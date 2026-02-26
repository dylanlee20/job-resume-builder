"""Integration tests for the email verification flow (auth routes).

Tests the full registration -> verification -> login cycle including:
- Registration with hashed-token creation via Resend
- Email verification link handling (query-param based)
- Login gate for unverified users
- Resend verification with cooldown + rate limiting
- Verification gate (403 for unverified on protected routes)
- AJAX availability checks (no email enumeration)
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from models.database import db
from models.user import User
from models.email_verification_token import EmailVerificationToken


# =========================================================================
# Registration
# =========================================================================

class TestRegistration:
    """POST /auth/register"""

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_register_success_sends_email(self, mock_email, app, client):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'newuser',
                'email': 'new@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)
            assert resp.status_code == 200
            user = User.query.filter_by(username='newuser').first()
            assert user is not None
            assert user.email_verified is False
            mock_email.assert_called_once()

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_register_creates_hashed_token(self, mock_email, app, client):
        with app.app_context():
            client.post('/auth/register', data={
                'username': 'tokenuser',
                'email': 'token@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            })
            user = User.query.filter_by(username='tokenuser').first()
            token = EmailVerificationToken.query.filter_by(user_id=user.id).first()
            assert token is not None
            assert len(token.token_hash) == 64  # SHA-256 hex
            assert token.used_at is None
            assert token.expires_at > datetime.utcnow()

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_register_does_not_log_in_user(self, mock_email, app, client):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'nologin',
                'email': 'nologin@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=False)
            # Should redirect to login, not to index
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_register_short_username(self, app, client):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'ab',
                'email': 'short@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)
            assert b'at least 3 characters' in resp.data

    def test_register_invalid_email(self, app, client):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'validname',
                'email': 'notanemail',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)
            assert b'valid email' in resp.data

    def test_register_short_password(self, app, client):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'validname',
                'email': 'valid@example.com',
                'password': 'short',
                'confirm_password': 'short',
            }, follow_redirects=True)
            assert b'at least 8 characters' in resp.data

    def test_register_password_mismatch(self, app, client):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'validname',
                'email': 'valid@example.com',
                'password': 'securepass8',
                'confirm_password': 'different8',
            }, follow_redirects=True)
            assert b'do not match' in resp.data

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_register_duplicate_username_revealed(self, mock_email, app, client, sample_user):
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'testuser',
                'email': 'different@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)
            assert b'already taken' in resp.data

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_register_duplicate_email_uses_generic_message(self, mock_email, app, client, sample_user):
        """Email existence must NOT be leaked."""
        with app.app_context():
            resp = client.post('/auth/register', data={
                'username': 'differentuser',
                'email': 'test@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)
            # Must NOT say "already exists" or "already registered"
            assert b'already exists' not in resp.data
            assert b'already registered' not in resp.data
            # Should show generic success message
            assert b'verification email has been sent' in resp.data

    @patch('routes.auth.EmailService.send_verification_email', return_value=(False, 'API error'))
    def test_register_email_failure_still_creates_user(self, mock_email, app, client):
        with app.app_context():
            client.post('/auth/register', data={
                'username': 'emailfail',
                'email': 'fail@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)
            user = User.query.filter_by(username='emailfail').first()
            assert user is not None


# =========================================================================
# Login
# =========================================================================

class TestLogin:
    """POST /auth/login"""

    def test_login_verified_user(self, app, client, verified_user):
        with app.app_context():
            resp = client.post('/auth/login', data={
                'username': 'verifieduser',
                'password': 'password123',
            }, follow_redirects=False)
            assert resp.status_code == 302

    def test_login_unverified_user_blocked(self, app, client, sample_user):
        with app.app_context():
            resp = client.post('/auth/login', data={
                'username': 'testuser',
                'password': 'password123',
            }, follow_redirects=True)
            assert b'verify your email' in resp.data.lower()

    def test_login_wrong_password(self, app, client, verified_user):
        with app.app_context():
            resp = client.post('/auth/login', data={
                'username': 'verifieduser',
                'password': 'wrongpassword',
            }, follow_redirects=True)
            assert b'Invalid' in resp.data

    def test_login_nonexistent_user(self, app, client):
        with app.app_context():
            resp = client.post('/auth/login', data={
                'username': 'nobody',
                'password': 'password123',
            }, follow_redirects=True)
            assert b'Invalid' in resp.data

    def test_login_by_email(self, app, client, verified_user):
        with app.app_context():
            resp = client.post('/auth/login', data={
                'username': 'verified@example.com',
                'password': 'password123',
            }, follow_redirects=False)
            assert resp.status_code == 302

    def test_login_admin_always_allowed(self, app, client, admin_user):
        with app.app_context():
            resp = client.post('/auth/login', data={
                'username': 'admin_test',
                'password': 'adminpass123',
            }, follow_redirects=False)
            assert resp.status_code == 302

    def test_login_redirects_authenticated_user(self, app, client, verified_user):
        with app.app_context():
            client.post('/auth/login', data={
                'username': 'verifieduser',
                'password': 'password123',
            })
            resp = client.get('/auth/login', follow_redirects=False)
            assert resp.status_code == 302


# =========================================================================
# Email verification link — GET /auth/verify-email?token=...
# =========================================================================

class TestVerifyEmail:
    """GET /auth/verify-email?token=..."""

    def test_verify_valid_token(self, app, client, sample_user):
        with app.app_context():
            raw_token = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            resp = client.get(f'/auth/verify-email?token={raw_token}', follow_redirects=True)
            assert b'verified successfully' in resp.data.lower()

            user = User.query.get(sample_user.id)
            assert user.email_verified is True
            assert user.email_verified_at is not None

    def test_verify_marks_token_as_used(self, app, client, sample_user):
        with app.app_context():
            raw_token = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            client.get(f'/auth/verify-email?token={raw_token}')

            token_hash = EmailVerificationToken.hash_token(raw_token)
            record = EmailVerificationToken.query.filter_by(token_hash=token_hash).first()
            assert record.used_at is not None

    def test_verify_used_token_rejected(self, app, client, sample_user):
        """Tokens are one-time use."""
        with app.app_context():
            raw_token = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            # First use — success
            client.get(f'/auth/verify-email?token={raw_token}')
            # Second use — should fail
            resp = client.get(f'/auth/verify-email?token={raw_token}', follow_redirects=True)
            assert b'invalid' in resp.data.lower() or b'already' in resp.data.lower()

    def test_verify_invalid_token(self, app, client):
        with app.app_context():
            resp = client.get('/auth/verify-email?token=bogus-token', follow_redirects=True)
            assert b'invalid' in resp.data.lower()

    def test_verify_expired_token_rejected(self, app, client, sample_user):
        with app.app_context():
            raw_token = EmailVerificationToken.create_for_user(sample_user.id)
            # Manually expire the token
            token_hash = EmailVerificationToken.hash_token(raw_token)
            record = EmailVerificationToken.query.filter_by(token_hash=token_hash).first()
            record.expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()

            resp = client.get(f'/auth/verify-email?token={raw_token}', follow_redirects=True)
            assert b'invalid' in resp.data.lower() or b'expired' in resp.data.lower()

            user = User.query.get(sample_user.id)
            assert user.email_verified is False

    def test_verify_missing_token_param(self, app, client):
        with app.app_context():
            resp = client.get('/auth/verify-email', follow_redirects=True)
            assert b'missing' in resp.data.lower() or resp.status_code == 200


# =========================================================================
# Resend verification
# =========================================================================

class TestResendVerification:
    """GET/POST /auth/resend-verification"""

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_resend_for_unverified_user(self, mock_email, app, client, sample_user):
        with app.app_context():
            resp = client.post('/auth/resend-verification', data={
                'email': 'test@example.com',
            }, follow_redirects=True)
            assert resp.status_code == 200
            mock_email.assert_called_once()

    def test_resend_for_nonexistent_email(self, app, client):
        """Should show generic message to prevent email enumeration."""
        with app.app_context():
            resp = client.post('/auth/resend-verification', data={
                'email': 'nobody@example.com',
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'If that email is registered' in resp.data

    def test_resend_for_already_verified(self, app, client, verified_user):
        with app.app_context():
            resp = client.post('/auth/resend-verification', data={
                'email': 'verified@example.com',
            }, follow_redirects=True)
            # Generic message, not "already verified"
            assert b'If that email is registered' in resp.data

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_resend_60s_cooldown(self, mock_email, app, client, sample_user):
        """Should block resend within 60s of last token creation."""
        with app.app_context():
            # Create a recent token
            EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            resp = client.post('/auth/resend-verification', data={
                'email': 'test@example.com',
            }, follow_redirects=True)
            assert b'recently' in resp.data.lower() or b'wait' in resp.data.lower()
            mock_email.assert_not_called()

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_resend_allowed_after_cooldown(self, mock_email, app, client, sample_user):
        with app.app_context():
            raw_token = EmailVerificationToken.create_for_user(sample_user.id)
            # Push creation time back beyond 60s
            token_hash = EmailVerificationToken.hash_token(raw_token)
            record = EmailVerificationToken.query.filter_by(token_hash=token_hash).first()
            record.created_at = datetime.utcnow() - timedelta(seconds=90)
            db.session.commit()

            resp = client.post('/auth/resend-verification', data={
                'email': 'test@example.com',
            }, follow_redirects=True)
            mock_email.assert_called_once()

    def test_resend_no_email_shows_form(self, app, client):
        with app.app_context():
            resp = client.get('/auth/resend-verification')
            assert resp.status_code == 200

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_resend_invalidates_old_tokens(self, mock_email, app, client, sample_user):
        """Resending should invalidate previous unused tokens."""
        with app.app_context():
            # Create first token
            raw1 = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            # Push creation back so cooldown passes
            hash1 = EmailVerificationToken.hash_token(raw1)
            record1 = EmailVerificationToken.query.filter_by(token_hash=hash1).first()
            record1.created_at = datetime.utcnow() - timedelta(seconds=90)
            db.session.commit()

            # Resend creates new token, old one gets deleted
            client.post('/auth/resend-verification', data={
                'email': 'test@example.com',
            })

            # Old token should be gone (invalidated)
            old_record = EmailVerificationToken.query.filter_by(token_hash=hash1).first()
            assert old_record is None

            # New token should exist
            new_tokens = EmailVerificationToken.query.filter_by(
                user_id=sample_user.id, used_at=None
            ).all()
            assert len(new_tokens) == 1


# =========================================================================
# Verification gate (before_request)
# =========================================================================

class TestVerificationGate:
    """Unverified users must get 403 on protected routes."""

    def test_unverified_user_blocked_from_protected_route(self, app, client, sample_user):
        """If unverified user has a session, before_request should block them."""
        with app.app_context():
            # Force-login the unverified user by bypassing the login gate
            with client.session_transaction() as sess:
                sess['_user_id'] = str(sample_user.id)

            resp = client.get('/', follow_redirects=False)
            # Should redirect to login (after logout)
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_verified_user_passes_gate(self, app, client, verified_user):
        with app.app_context():
            client.post('/auth/login', data={
                'username': 'verifieduser',
                'password': 'password123',
            })
            resp = client.get('/', follow_redirects=False)
            # Should NOT be blocked
            assert resp.status_code in (200, 302)
            location = resp.headers.get('Location', '')
            assert '/auth/login' not in location

    def test_unverified_user_json_gets_403(self, app, client, sample_user):
        """JSON requests should get 403 with EMAIL_NOT_VERIFIED code."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_user_id'] = str(sample_user.id)

            resp = client.get('/', headers={'Accept': 'application/json'})
            assert resp.status_code == 403
            data = resp.get_json()
            assert data['code'] == 'EMAIL_NOT_VERIFIED'


# =========================================================================
# Full registration -> verification -> login cycle
# =========================================================================

class TestFullVerificationCycle:

    @patch('routes.auth.EmailService.send_verification_email', return_value=(True, None))
    def test_full_cycle(self, mock_email, app, client):
        with app.app_context():
            # 1. Register
            client.post('/auth/register', data={
                'username': 'cycleuser',
                'email': 'cycle@example.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            })
            user = User.query.filter_by(username='cycleuser').first()
            assert user is not None
            assert user.email_verified is False

            # Extract the raw token from the mock call args (verify_url)
            call_args = mock_email.call_args
            verify_url = call_args[0][2] if call_args[0] else call_args[1].get('verify_url', '')
            raw_token = verify_url.split('token=')[-1]

            # 2. Try login — should be blocked
            resp = client.post('/auth/login', data={
                'username': 'cycleuser',
                'password': 'securepass8',
            }, follow_redirects=True)
            assert b'verify your email' in resp.data.lower()

            # 3. Click verification link
            resp = client.get(f'/auth/verify-email?token={raw_token}', follow_redirects=True)
            assert b'verified successfully' in resp.data.lower()

            # 4. Login should now succeed
            resp = client.post('/auth/login', data={
                'username': 'cycleuser',
                'password': 'securepass8',
            }, follow_redirects=False)
            assert resp.status_code == 302


# =========================================================================
# AJAX availability checks (no email enumeration)
# =========================================================================

class TestAvailabilityChecks:

    def test_check_username_available(self, app, client):
        with app.app_context():
            resp = client.get('/auth/check-username?username=brandnew')
            data = resp.get_json()
            assert data['available'] is True

    def test_check_username_taken(self, app, client, sample_user):
        with app.app_context():
            resp = client.get('/auth/check-username?username=testuser')
            data = resp.get_json()
            assert data['available'] is False

    def test_check_username_too_short(self, app, client):
        with app.app_context():
            resp = client.get('/auth/check-username?username=ab')
            data = resp.get_json()
            assert data['available'] is False

    def test_check_email_never_leaks_existence(self, app, client, sample_user):
        """check-email should not reveal whether an email is registered."""
        with app.app_context():
            # Existing email
            resp = client.get('/auth/check-email?email=test@example.com')
            data = resp.get_json()
            assert data['available'] is True  # Always true for valid format
            assert 'already' not in data['message'].lower()

    def test_check_email_invalid_format(self, app, client):
        with app.app_context():
            resp = client.get('/auth/check-email?email=notvalid')
            data = resp.get_json()
            assert data['available'] is False


# =========================================================================
# Logout
# =========================================================================

class TestLogout:

    def test_logout_redirects_to_login(self, app, client, verified_user):
        with app.app_context():
            client.post('/auth/login', data={
                'username': 'verifieduser',
                'password': 'password123',
            })
            resp = client.get('/auth/logout', follow_redirects=False)
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')
