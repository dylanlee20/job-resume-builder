"""
Tests for the email verification flow.

Covers:
- Token generation, hashing, expiry, and single-use enforcement
- Registration → unverified → cannot login → verify → can login
- Resend verification with rate limiting
- Edge cases (expired tokens, replayed tokens, unknown tokens)
"""
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from models.database import db
from models.user import User
from services.email_service import EmailService


# ---------------------------------------------------------------------------
# Unit tests for EmailService token helpers
# ---------------------------------------------------------------------------

class TestTokenGeneration:
    """Unit tests for token generation and hashing."""

    def test_generate_token_is_url_safe_string(self, app):
        with app.app_context():
            token = EmailService.generate_verification_token()
            assert isinstance(token, str)
            assert len(token) > 32  # 48 bytes → ~64 chars base64

    def test_tokens_are_unique(self, app):
        with app.app_context():
            tokens = {EmailService.generate_verification_token() for _ in range(50)}
            assert len(tokens) == 50

    def test_hash_token_returns_sha256_hex(self, app):
        with app.app_context():
            token = 'test-token-123'
            expected = hashlib.sha256(token.encode('utf-8')).hexdigest()
            assert EmailService.hash_token(token) == expected

    def test_hash_token_deterministic(self, app):
        with app.app_context():
            token = EmailService.generate_verification_token()
            assert EmailService.hash_token(token) == EmailService.hash_token(token)


# ---------------------------------------------------------------------------
# Unit tests for verify_token logic
# ---------------------------------------------------------------------------

class TestVerifyToken:
    """Unit tests for token verification (expiry, single-use, etc.)."""

    def _create_user(self, token_plaintext, sent_at=None):
        """Helper: create a user with a hashed verification token."""
        user = User(
            username='testuser',
            email='test@example.com',
            email_verified=False,
            email_verification_token=EmailService.hash_token(token_plaintext),
            email_verification_sent_at=sent_at or datetime.utcnow(),
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user

    def test_valid_token_verifies_user(self, app):
        with app.app_context():
            token = 'valid-token-abc'
            user = self._create_user(token)
            success, message, returned_user = EmailService.verify_token(token)
            assert success is True
            assert returned_user.id == user.id
            assert returned_user.email_verified is True

    def test_verified_token_is_invalidated(self, app):
        """Token must be single-use: after verification, the same token must fail."""
        with app.app_context():
            token = 'single-use-token'
            self._create_user(token)

            # First call succeeds
            success, _, _ = EmailService.verify_token(token)
            assert success is True

            # Second call fails (token was set to None)
            success, message, user = EmailService.verify_token(token)
            assert success is False
            assert 'Invalid' in message

    def test_unknown_token_rejected(self, app):
        with app.app_context():
            success, message, user = EmailService.verify_token('no-such-token')
            assert success is False
            assert user is None

    def test_expired_token_rejected(self, app):
        with app.app_context():
            token = 'expired-token'
            sent_at = datetime.utcnow() - timedelta(hours=25)
            user = self._create_user(token, sent_at=sent_at)

            success, message, returned_user = EmailService.verify_token(token)
            assert success is False
            assert 'expired' in message.lower()
            assert returned_user.id == user.id
            assert returned_user.email_verified is False

    def test_already_verified_returns_success(self, app):
        with app.app_context():
            token = 'already-verified-token'
            user = self._create_user(token)
            user.email_verified = True
            db.session.commit()

            success, message, _ = EmailService.verify_token(token)
            assert success is True
            assert 'already verified' in message.lower()


# ---------------------------------------------------------------------------
# Unit tests for resend rate limiting
# ---------------------------------------------------------------------------

class TestCanResend:
    """Unit tests for resend rate limiting."""

    def test_can_resend_when_never_sent(self, app):
        with app.app_context():
            user = User(
                username='u1', email='u1@example.com',
                email_verification_sent_at=None
            )
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

            can, wait = EmailService.can_resend(user)
            assert can is True
            assert wait == 0

    def test_cannot_resend_within_60_seconds(self, app):
        with app.app_context():
            user = User(
                username='u2', email='u2@example.com',
                email_verification_sent_at=datetime.utcnow() - timedelta(seconds=10)
            )
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

            can, wait = EmailService.can_resend(user)
            assert can is False
            assert wait > 0

    def test_can_resend_after_60_seconds(self, app):
        with app.app_context():
            user = User(
                username='u3', email='u3@example.com',
                email_verification_sent_at=datetime.utcnow() - timedelta(seconds=61)
            )
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

            can, wait = EmailService.can_resend(user)
            assert can is True


# ---------------------------------------------------------------------------
# Integration tests — registration → verification → login
# ---------------------------------------------------------------------------

class TestRegistrationFlow:
    """Integration tests for the full registration / verification / login flow."""

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_register_creates_unverified_user(self, mock_send, client, app):
        resp = client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        }, follow_redirects=False)

        assert resp.status_code in (302, 303)
        assert '/verification-pending' in resp.headers['Location']

        with app.app_context():
            user = User.query.filter_by(username='newuser').first()
            assert user is not None
            assert user.email_verified is False
            assert user.email_verification_token is not None
            mock_send.assert_called_once()

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_unverified_user_cannot_login(self, mock_send, client, app):
        # Register
        client.post('/register', data={
            'username': 'blocked',
            'email': 'blocked@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        # Attempt login
        resp = client.post('/login', data={
            'username': 'blocked',
            'password': 'secure123',
        }, follow_redirects=True)

        assert b'verify your email' in resp.data.lower()

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_verified_user_can_login(self, mock_send, client, app):
        # Register
        client.post('/register', data={
            'username': 'gooduser',
            'email': 'good@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        # Manually verify (simulate clicking email link)
        with app.app_context():
            user = User.query.filter_by(username='gooduser').first()
            user.email_verified = True
            user.email_verification_token = None
            db.session.commit()

        # Login should succeed
        resp = client.post('/login', data={
            'username': 'gooduser',
            'password': 'secure123',
        }, follow_redirects=False)

        assert resp.status_code in (302, 303)
        assert '/login' not in resp.headers['Location']

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_verify_email_endpoint(self, mock_send, client, app):
        """Full flow: register → capture token → verify via endpoint → login."""
        # Register
        client.post('/register', data={
            'username': 'flowuser',
            'email': 'flow@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        # Extract the plaintext token from the _send_email mock call
        # The verify URL is embedded in the HTML body
        html_body = mock_send.call_args[0][2]  # third positional arg
        import re
        match = re.search(r'/verify-email/([A-Za-z0-9_-]+)', html_body)
        assert match, "Verification URL not found in email body"
        token = match.group(1)

        # Hit the verify endpoint
        resp = client.get(f'/verify-email/{token}', follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert '/login' in resp.headers['Location']

        # User should now be verified
        with app.app_context():
            user = User.query.filter_by(username='flowuser').first()
            assert user.email_verified is True
            assert user.email_verification_token is None

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_replay_token_after_verification_fails(self, mock_send, client, app):
        """Replaying a used verification link must fail."""
        client.post('/register', data={
            'username': 'replayuser',
            'email': 'replay@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        html_body = mock_send.call_args[0][2]
        import re
        match = re.search(r'/verify-email/([A-Za-z0-9_-]+)', html_body)
        token = match.group(1)

        # First use — succeeds
        resp = client.get(f'/verify-email/{token}', follow_redirects=True)
        assert b'verified' in resp.data.lower() or b'sign in' in resp.data.lower()

        # Second use — must fail
        resp = client.get(f'/verify-email/{token}', follow_redirects=True)
        assert b'invalid' in resp.data.lower() or b'expired' in resp.data.lower()


class TestResendVerification:
    """Integration tests for the resend verification endpoint."""

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_resend_sends_new_email(self, mock_send, client, app):
        # Register first
        client.post('/register', data={
            'username': 'resenduser',
            'email': 'resend@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        # Reset the sent_at to bypass rate limit
        with app.app_context():
            user = User.query.filter_by(username='resenduser').first()
            user.email_verification_sent_at = datetime.utcnow() - timedelta(seconds=120)
            db.session.commit()

        mock_send.reset_mock()

        resp = client.get(
            '/resend-verification?email=resend@example.com',
            follow_redirects=True
        )

        assert mock_send.called
        assert b'resent' in resp.data.lower() or b'check your inbox' in resp.data.lower()

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_resend_rate_limited(self, mock_send, client, app):
        # Register
        client.post('/register', data={
            'username': 'ratelimited',
            'email': 'rate@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        mock_send.reset_mock()

        # Immediately try to resend (within 60s window)
        resp = client.get(
            '/resend-verification?email=rate@example.com',
            follow_redirects=True
        )

        assert not mock_send.called
        assert b'wait' in resp.data.lower()

    def test_resend_unknown_email_safe_message(self, client):
        """Must not reveal whether the email is registered."""
        resp = client.get(
            '/resend-verification?email=nobody@example.com',
            follow_redirects=True
        )
        # Should say something generic, not "email not found"
        assert b'not found' not in resp.data.lower()
        assert b'not registered' not in resp.data.lower()

    @patch.object(EmailService, '_send_email', return_value=True)
    def test_resend_already_verified_redirects_to_login(self, mock_send, client, app):
        client.post('/register', data={
            'username': 'verifiedresend',
            'email': 'vresend@example.com',
            'password': 'secure123',
            'confirm_password': 'secure123',
        })

        with app.app_context():
            user = User.query.filter_by(email='vresend@example.com').first()
            user.email_verified = True
            db.session.commit()

        mock_send.reset_mock()

        resp = client.get(
            '/resend-verification?email=vresend@example.com',
            follow_redirects=False
        )

        assert '/login' in resp.headers['Location']
        assert not mock_send.called
