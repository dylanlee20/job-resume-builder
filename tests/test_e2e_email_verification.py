"""E2E test: Real email verification flow with actual SMTP capture.

Unlike the unit tests which mock emails, this test:
1. Starts a REAL local SMTP server that captures emails
2. Configures Flask to send through that server
3. Registers a user → real email is sent and captured
4. Extracts the verification link from the captured email
5. Clicks the link → user gets verified
6. Logs in successfully

You will see the actual email content printed in the test output.
"""
import email
import re
import threading
import time
from asyncio import new_event_loop

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from aiosmtpd.smtp import AuthResult, LoginPassword

from models.database import db
from models.user import User


# =========================================================================
# Local SMTP capture server with AUTH support
# =========================================================================

def _accept_any_auth(server, session, envelope, mechanism, auth_data):
    """Accept any login credentials — this is a test server."""
    return AuthResult(success=True)


class EmailCaptureHandler(Message):
    """Captures all emails sent to this SMTP server."""

    def __init__(self):
        super().__init__()
        self.captured_emails = []

    def handle_message(self, message):
        """Called for every email received by the SMTP server."""
        self.captured_emails.append(message)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture(scope='module')
def smtp_handler():
    """Email capture handler that stores all received emails."""
    return EmailCaptureHandler()


@pytest.fixture(scope='module')
def smtp_server(smtp_handler):
    """Start a real local SMTP server on port 9025 with AUTH support."""
    controller = Controller(
        smtp_handler,
        hostname='127.0.0.1',
        port=9025,
        authenticator=_accept_any_auth,
        auth_require_tls=False,  # Allow AUTH without TLS for local testing
    )
    controller.start()
    # Give the server a moment to bind
    time.sleep(0.3)
    yield controller
    controller.stop()


@pytest.fixture()
def e2e_app(smtp_server):
    """Flask app configured to send through the local SMTP capture server."""
    import os
    os.environ['SECRET_KEY'] = 'e2e-test-secret'
    os.environ['ADMIN_PASSWORD'] = 'testadmin123'
    os.environ['DISABLE_SCHEDULER'] = 'true'

    from app import create_app
    flask_app, _scheduler = create_app()
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost:5000',
    })

    # Point Flask's email config at our local SMTP capture server
    from config import Config
    Config.MAIL_SERVER = '127.0.0.1'
    Config.MAIL_PORT = 9025
    Config.MAIL_USE_TLS = False  # Local server, no TLS needed
    Config.MAIL_USERNAME = 'test@localhost'
    Config.MAIL_PASSWORD = 'testpass'
    Config.MAIL_DEFAULT_SENDER = 'noreply@newwhale-test.com'
    Config.SITE_URL = 'http://localhost:5000'

    with flask_app.app_context():
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.rollback()
        db.drop_all()

    # Reset Config values
    Config.MAIL_USE_TLS = True


@pytest.fixture()
def e2e_client(e2e_app):
    """Test client for E2E app."""
    return e2e_app.test_client()


# =========================================================================
# Helper: extract verification link from captured email
# =========================================================================

def extract_verify_link(captured_email):
    """Pull the /auth/verify-email/<token> URL from a captured email."""
    # Get the email body (try HTML first, then plain text)
    body = ''
    if captured_email.is_multipart():
        for part in captured_email.walk():
            content_type = part.get_content_type()
            if content_type == 'text/html':
                body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                break
            elif content_type == 'text/plain':
                body = part.get_payload(decode=True).decode('utf-8', errors='replace')
    else:
        body = captured_email.get_payload(decode=True).decode('utf-8', errors='replace')

    # Find the verification URL
    match = re.search(r'(https?://[^\s"<>]+/auth/verify-email/[A-Za-z0-9_-]+)', body)
    if match:
        return match.group(1)
    return None


# =========================================================================
# E2E Tests
# =========================================================================

class TestE2EEmailVerification:
    """Full end-to-end email verification with real SMTP."""

    def test_full_registration_to_login_with_real_email(
        self, e2e_app, e2e_client, smtp_handler
    ):
        """
        FULL CYCLE:
        1. Register a new user
        2. Real email is sent and captured by local SMTP server
        3. Extract verification link from email
        4. Click the link
        5. Login succeeds
        """
        # Clear any previously captured emails
        smtp_handler.captured_emails.clear()

        with e2e_app.app_context():
            # ----------------------------------------------------------
            # STEP 1: Register
            # ----------------------------------------------------------
            resp = e2e_client.post('/auth/register', data={
                'username': 'realemailuser',
                'email': 'realemailuser@test.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)

            assert resp.status_code == 200
            user = User.query.filter_by(username='realemailuser').first()
            assert user is not None
            assert user.email_verified is False

            # ----------------------------------------------------------
            # STEP 2: Verify a REAL email was captured
            # ----------------------------------------------------------
            # Give SMTP a moment to process
            time.sleep(0.5)

            assert len(smtp_handler.captured_emails) >= 1, \
                "No email was captured! SMTP server received nothing."

            captured = smtp_handler.captured_emails[-1]

            # Print the email so you can see it in test output
            print("\n" + "=" * 60)
            print("CAPTURED EMAIL")
            print("=" * 60)
            print(f"  From:    {captured['From']}")
            print(f"  To:      {captured['To']}")
            print(f"  Subject: {captured['Subject']}")
            print("-" * 60)

            # Show plain text body
            if captured.is_multipart():
                for part in captured.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        print(body)
                        break
            else:
                print(captured.get_payload(decode=True).decode('utf-8', errors='replace'))
            print("=" * 60 + "\n")

            # Verify email metadata
            assert captured['To'] == 'realemailuser@test.com'
            assert 'verify' in captured['Subject'].lower() or 'newwhale' in captured['Subject'].lower()

            # ----------------------------------------------------------
            # STEP 3: Extract verification link from email
            # ----------------------------------------------------------
            verify_url = extract_verify_link(captured)
            assert verify_url is not None, \
                "Could not find verification link in email body!"
            print(f"  Extracted link: {verify_url}")

            # Extract just the path (e.g., /auth/verify-email/TOKEN)
            verify_path = verify_url.replace('http://localhost:5000', '')

            # ----------------------------------------------------------
            # STEP 4: Click the verification link
            # ----------------------------------------------------------
            resp = e2e_client.get(verify_path, follow_redirects=True)
            assert resp.status_code == 200
            assert b'verified successfully' in resp.data.lower()

            # Confirm DB was updated
            user = User.query.filter_by(username='realemailuser').first()
            assert user.email_verified is True
            print("  Email verified in database: YES")

            # ----------------------------------------------------------
            # STEP 5: Login should now succeed
            # ----------------------------------------------------------
            resp = e2e_client.post('/auth/login', data={
                'username': 'realemailuser',
                'password': 'securepass8',
            }, follow_redirects=False)

            assert resp.status_code == 302, \
                "Login should redirect (302) on success"
            print("  Login after verification: SUCCESS")
            print("\n  E2E RESULT: PASS")

    def test_unverified_user_blocked_real_email_flow(
        self, e2e_app, e2e_client, smtp_handler
    ):
        """Register but DON'T click the link — login should be blocked."""
        smtp_handler.captured_emails.clear()

        with e2e_app.app_context():
            # Register
            e2e_client.post('/auth/register', data={
                'username': 'blockeduser',
                'email': 'blocked@test.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            })

            time.sleep(0.3)

            # Email was sent
            assert len(smtp_handler.captured_emails) >= 1

            # Try to login WITHOUT verifying
            resp = e2e_client.post('/auth/login', data={
                'username': 'blockeduser',
                'password': 'securepass8',
            }, follow_redirects=True)

            assert b'verify your email' in resp.data.lower(), \
                "Unverified user should see verification warning"
            print("\n  Unverified login blocked: CORRECT")

    def test_resend_sends_new_real_email(
        self, e2e_app, e2e_client, smtp_handler
    ):
        """Resend verification should send a real second email."""
        smtp_handler.captured_emails.clear()

        with e2e_app.app_context():
            # Register (sends first email)
            e2e_client.post('/auth/register', data={
                'username': 'resenduser',
                'email': 'resend@test.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            })
            time.sleep(0.5)
            first_count = len(smtp_handler.captured_emails)
            assert first_count >= 1, "First email not captured"

            # Fast-forward the rate limit by updating the DB directly
            user = User.query.filter_by(username='resenduser').first()
            from datetime import datetime, timedelta
            user.email_verification_sent_at = datetime.utcnow() - timedelta(minutes=5)
            db.session.commit()

            # Resend
            e2e_client.post('/auth/resend-verification', data={
                'email': 'resend@test.com',
            }, follow_redirects=True)
            time.sleep(0.5)

            assert len(smtp_handler.captured_emails) > first_count, \
                "Resend did not produce a new email!"

            # The new email should have a DIFFERENT token
            first_link = extract_verify_link(smtp_handler.captured_emails[0])
            second_link = extract_verify_link(smtp_handler.captured_emails[-1])
            assert first_link != second_link, \
                "Resend should generate a new token"
            print(f"\n  First link:  {first_link}")
            print(f"  Second link: {second_link}")
            print("  New token generated: YES")

    def test_expired_link_rejected_real_flow(
        self, e2e_app, e2e_client, smtp_handler
    ):
        """Register, expire the token manually, click link — should fail."""
        smtp_handler.captured_emails.clear()

        with e2e_app.app_context():
            # Register
            e2e_client.post('/auth/register', data={
                'username': 'expireduser',
                'email': 'expired@test.com',
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            })
            time.sleep(0.5)

            assert len(smtp_handler.captured_emails) >= 1
            verify_url = extract_verify_link(smtp_handler.captured_emails[-1])
            verify_path = verify_url.replace('http://localhost:5000', '')

            # Expire the token by pushing sent_at back 25 hours
            user = User.query.filter_by(username='expireduser').first()
            from datetime import datetime, timedelta
            user.email_verification_sent_at = datetime.utcnow() - timedelta(hours=25)
            db.session.commit()

            # Click the expired link
            resp = e2e_client.get(verify_path, follow_redirects=True)
            assert b'expired' in resp.data.lower()

            # User should still be unverified
            user = User.query.filter_by(username='expireduser').first()
            assert user.email_verified is False
            print("\n  Expired link rejected: CORRECT")
