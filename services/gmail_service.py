"""Gmail OAuth + send service for BYO mailbox outreach."""
import base64
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

from config import Config
from models.database import db

logger = logging.getLogger(__name__)


class GmailService:
    """Google OAuth and Gmail API helpers."""

    OAUTH_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
    USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
    GMAIL_SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
    SCOPES = (
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/userinfo.email',
    )

    @classmethod
    def is_configured(cls):
        """Return True when OAuth client credentials are configured."""
        return bool(Config.GOOGLE_CLIENT_ID and Config.GOOGLE_CLIENT_SECRET)

    @classmethod
    def get_redirect_uri(cls):
        """Return the configured OAuth callback URL."""
        if Config.GOOGLE_OAUTH_REDIRECT_URI:
            return Config.GOOGLE_OAUTH_REDIRECT_URI
        base = (Config.APP_BASE_URL or '').rstrip('/') or 'http://localhost:5000'
        return f'{base}/outreach/gmail/callback'

    @classmethod
    def build_authorization_url(cls, state):
        """Build the Google OAuth authorization URL."""
        if not cls.is_configured():
            raise RuntimeError('Google OAuth is not configured.')

        params = {
            'client_id': Config.GOOGLE_CLIENT_ID,
            'redirect_uri': cls.get_redirect_uri(),
            'response_type': 'code',
            'scope': ' '.join(cls.SCOPES),
            'access_type': 'offline',
            'include_granted_scopes': 'true',
            'prompt': 'consent',
            'state': state,
        }
        return f'{cls.OAUTH_AUTHORIZE_URL}?{urlencode(params)}'

    @staticmethod
    def _extract_error(resp):
        """Extract a useful error message from a Google API response."""
        try:
            payload = resp.json()
        except Exception:
            payload = {}

        if isinstance(payload, dict):
            err = payload.get('error')
            if isinstance(err, dict):
                return err.get('message') or str(err)
            if isinstance(err, str):
                detail = payload.get('error_description')
                return f'{err}: {detail}' if detail else err
        return resp.text or f'HTTP {resp.status_code}'

    @classmethod
    def exchange_code_for_tokens(cls, code):
        """Exchange OAuth code for access/refresh tokens."""
        resp = requests.post(
            cls.OAUTH_TOKEN_URL,
            data={
                'code': code,
                'client_id': Config.GOOGLE_CLIENT_ID,
                'client_secret': Config.GOOGLE_CLIENT_SECRET,
                'redirect_uri': cls.get_redirect_uri(),
                'grant_type': 'authorization_code',
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f'Google token exchange failed: {cls._extract_error(resp)}')
        return resp.json()

    @classmethod
    def fetch_user_email(cls, access_token):
        """Fetch connected Google account email."""
        resp = requests.get(
            cls.USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=20,
        )
        if not resp.ok:
            raise RuntimeError(f'Google user info failed: {cls._extract_error(resp)}')
        payload = resp.json()
        return (payload.get('email') or '').strip().lower() or None

    @staticmethod
    def _apply_token_payload(user, token_payload):
        """Apply token payload fields to user model."""
        now = datetime.utcnow()

        access_token = token_payload.get('access_token')
        if access_token:
            user.gmail_access_token = access_token

        refresh_token = token_payload.get('refresh_token')
        if refresh_token:
            user.gmail_refresh_token = refresh_token

        expires_in = token_payload.get('expires_in')
        if expires_in is not None:
            user.gmail_token_expiry = now + timedelta(seconds=int(expires_in))

        scope = token_payload.get('scope')
        if scope:
            user.gmail_scope = scope

    @classmethod
    def connect_user_with_code(cls, user, code):
        """Exchange OAuth code and persist Gmail credentials for a user."""
        token_payload = cls.exchange_code_for_tokens(code)
        cls._apply_token_payload(user, token_payload)

        access_token = user.gmail_access_token
        if not access_token:
            raise RuntimeError('Google OAuth response did not include an access token.')

        gmail_email = cls.fetch_user_email(access_token)
        user.gmail_email = gmail_email
        if gmail_email and not user.sender_email:
            user.sender_email = gmail_email
        user.gmail_verified_at = datetime.utcnow()
        db.session.commit()
        return gmail_email

    @classmethod
    def refresh_access_token(cls, user):
        """Refresh expired access token using stored refresh token."""
        if not user.gmail_refresh_token:
            raise RuntimeError('Missing Gmail refresh token. Reconnect Gmail.')

        resp = requests.post(
            cls.OAUTH_TOKEN_URL,
            data={
                'client_id': Config.GOOGLE_CLIENT_ID,
                'client_secret': Config.GOOGLE_CLIENT_SECRET,
                'refresh_token': user.gmail_refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f'Google token refresh failed: {cls._extract_error(resp)}')

        cls._apply_token_payload(user, resp.json())
        db.session.commit()
        return user.gmail_access_token

    @classmethod
    def get_valid_access_token(cls, user):
        """Return a non-expired access token, refreshing when needed."""
        if not cls.is_configured():
            raise RuntimeError('Google OAuth is not configured.')

        now = datetime.utcnow()
        if (
            user.gmail_access_token
            and user.gmail_token_expiry
            and user.gmail_token_expiry > now + timedelta(seconds=90)
        ):
            return user.gmail_access_token

        if user.gmail_access_token and not user.gmail_token_expiry:
            return user.gmail_access_token

        return cls.refresh_access_token(user)

    @classmethod
    def send_mime_message(cls, user, mime_message):
        """Send a MIME email via Gmail API."""
        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()

        token = cls.get_valid_access_token(user)
        resp = requests.post(
            cls.GMAIL_SEND_URL,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'raw': raw},
            timeout=30,
        )

        # Access token may have expired unexpectedly; refresh once and retry.
        if resp.status_code == 401 and user.gmail_refresh_token:
            logger.info("Gmail access token rejected; refreshing and retrying send for user_id=%s", user.id)
            token = cls.refresh_access_token(user)
            resp = requests.post(
                cls.GMAIL_SEND_URL,
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                json={'raw': raw},
                timeout=30,
            )

        if not resp.ok:
            raise RuntimeError(f'Gmail send failed: {cls._extract_error(resp)}')
        return resp.json()

    @staticmethod
    def disconnect_user(user):
        """Remove all Gmail OAuth credentials from a user profile."""
        user.gmail_email = None
        user.gmail_access_token = None
        user.gmail_refresh_token = None
        user.gmail_token_expiry = None
        user.gmail_scope = None
        user.gmail_verified_at = None
        db.session.commit()
