"""Microsoft Outlook OAuth + Graph send service for BYO mailbox outreach."""
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

from config import Config
from models.database import db

logger = logging.getLogger(__name__)


class OutlookService:
    """Microsoft OAuth and Graph Mail API helpers."""

    OAUTH_AUTHORIZE_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    OAUTH_TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    GRAPH_ME_URL = 'https://graph.microsoft.com/v1.0/me'
    GRAPH_SEND_URL = 'https://graph.microsoft.com/v1.0/me/sendMail'
    SCOPES = (
        'offline_access',
        'openid',
        'profile',
        'email',
        'User.Read',
        'Mail.Send',
    )

    @classmethod
    def is_configured(cls):
        """Return True when Microsoft OAuth client credentials are configured."""
        return bool(Config.MICROSOFT_CLIENT_ID and Config.MICROSOFT_CLIENT_SECRET)

    @classmethod
    def get_redirect_uri(cls):
        """Return configured Outlook OAuth callback URL."""
        if Config.MICROSOFT_OAUTH_REDIRECT_URI:
            return Config.MICROSOFT_OAUTH_REDIRECT_URI
        base = (Config.APP_BASE_URL or '').rstrip('/') or 'http://localhost:5000'
        return f'{base}/outreach/outlook/callback'

    @classmethod
    def build_authorization_url(cls, state):
        """Build Microsoft OAuth authorization URL."""
        if not cls.is_configured():
            raise RuntimeError('Microsoft OAuth is not configured.')

        params = {
            'client_id': Config.MICROSOFT_CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': cls.get_redirect_uri(),
            'response_mode': 'query',
            'scope': ' '.join(cls.SCOPES),
            'state': state,
            'prompt': 'consent',
        }
        return f'{cls.OAUTH_AUTHORIZE_URL}?{urlencode(params)}'

    @staticmethod
    def _extract_error(resp):
        """Extract a useful error message from Microsoft responses."""
        try:
            payload = resp.json()
        except Exception:
            payload = {}

        if isinstance(payload, dict):
            err = payload.get('error')
            if isinstance(err, dict):
                return err.get('message') or str(err)
            if isinstance(err, str):
                detail = payload.get('error_description') or payload.get('message')
                return f'{err}: {detail}' if detail else err
        return resp.text or f'HTTP {resp.status_code}'

    @classmethod
    def exchange_code_for_tokens(cls, code):
        """Exchange OAuth code for access/refresh tokens."""
        resp = requests.post(
            cls.OAUTH_TOKEN_URL,
            data={
                'client_id': Config.MICROSOFT_CLIENT_ID,
                'client_secret': Config.MICROSOFT_CLIENT_SECRET,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': cls.get_redirect_uri(),
                'scope': ' '.join(cls.SCOPES),
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f'Microsoft token exchange failed: {cls._extract_error(resp)}')
        return resp.json()

    @classmethod
    def fetch_user_email(cls, access_token):
        """Fetch connected Microsoft account email."""
        resp = requests.get(
            cls.GRAPH_ME_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=20,
        )
        if not resp.ok:
            raise RuntimeError(f'Microsoft Graph profile fetch failed: {cls._extract_error(resp)}')
        payload = resp.json()
        email = (
            (payload.get('mail') or '').strip().lower()
            or (payload.get('userPrincipalName') or '').strip().lower()
        )
        return email or None

    @staticmethod
    def _apply_token_payload(user, token_payload):
        """Apply token payload fields to user model."""
        now = datetime.utcnow()

        access_token = token_payload.get('access_token')
        if access_token:
            user.outlook_access_token = access_token

        refresh_token = token_payload.get('refresh_token')
        if refresh_token:
            user.outlook_refresh_token = refresh_token

        expires_in = token_payload.get('expires_in')
        if expires_in is not None:
            user.outlook_token_expiry = now + timedelta(seconds=int(expires_in))

        scope = token_payload.get('scope')
        if scope:
            user.outlook_scope = scope

    @classmethod
    def connect_user_with_code(cls, user, code):
        """Exchange OAuth code and persist Outlook credentials for a user."""
        token_payload = cls.exchange_code_for_tokens(code)
        cls._apply_token_payload(user, token_payload)

        access_token = user.outlook_access_token
        if not access_token:
            raise RuntimeError('Microsoft OAuth response did not include an access token.')

        outlook_email = cls.fetch_user_email(access_token)
        user.outlook_email = outlook_email
        if outlook_email and not user.sender_email:
            user.sender_email = outlook_email
        user.outlook_verified_at = datetime.utcnow()
        db.session.commit()
        return outlook_email

    @classmethod
    def refresh_access_token(cls, user):
        """Refresh expired access token using stored refresh token."""
        if not user.outlook_refresh_token:
            raise RuntimeError('Missing Outlook refresh token. Reconnect Outlook.')

        resp = requests.post(
            cls.OAUTH_TOKEN_URL,
            data={
                'client_id': Config.MICROSOFT_CLIENT_ID,
                'client_secret': Config.MICROSOFT_CLIENT_SECRET,
                'grant_type': 'refresh_token',
                'refresh_token': user.outlook_refresh_token,
                'redirect_uri': cls.get_redirect_uri(),
                'scope': ' '.join(cls.SCOPES),
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f'Microsoft token refresh failed: {cls._extract_error(resp)}')

        cls._apply_token_payload(user, resp.json())
        db.session.commit()
        return user.outlook_access_token

    @classmethod
    def get_valid_access_token(cls, user):
        """Return a non-expired access token, refreshing when needed."""
        if not cls.is_configured():
            raise RuntimeError('Microsoft OAuth is not configured.')

        now = datetime.utcnow()
        if (
            user.outlook_access_token
            and user.outlook_token_expiry
            and user.outlook_token_expiry > now + timedelta(seconds=90)
        ):
            return user.outlook_access_token

        if user.outlook_access_token and not user.outlook_token_expiry:
            return user.outlook_access_token

        return cls.refresh_access_token(user)

    @classmethod
    def send_email(cls, user, to_email, subject, body_html, attachments=None):
        """Send email via Microsoft Graph Mail API."""
        token = cls.get_valid_access_token(user)
        payload = {
            'message': {
                'subject': subject,
                'body': {
                    'contentType': 'HTML',
                    'content': body_html,
                },
                'toRecipients': [
                    {'emailAddress': {'address': to_email}},
                ],
            },
            'saveToSentItems': True,
        }

        if attachments:
            payload['message']['attachments'] = attachments

        resp = requests.post(
            cls.GRAPH_SEND_URL,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=30,
        )

        # Access token can expire unexpectedly; refresh once and retry.
        if resp.status_code == 401 and user.outlook_refresh_token:
            logger.info("Outlook access token rejected; refreshing and retrying send for user_id=%s", user.id)
            token = cls.refresh_access_token(user)
            resp = requests.post(
                cls.GRAPH_SEND_URL,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=30,
            )

        if not resp.ok:
            raise RuntimeError(f'Outlook send failed: {cls._extract_error(resp)}')
        return {'ok': True}

    @staticmethod
    def disconnect_user(user):
        """Remove all Outlook OAuth credentials from a user profile."""
        user.outlook_email = None
        user.outlook_access_token = None
        user.outlook_refresh_token = None
        user.outlook_token_expiry = None
        user.outlook_scope = None
        user.outlook_verified_at = None
        db.session.commit()
