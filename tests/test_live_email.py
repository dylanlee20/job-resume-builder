"""LIVE E2E test: Send a REAL verification email through Outlook SMTP.

This test sends an actual email to a real inbox. Run it manually:

    MAIL_PASSWORD='your_password' python3 -m pytest tests/test_live_email.py -v -s

You will receive a real email at the configured address.
Check your inbox (and spam folder) after running.
"""
import os
import re
import time

import pytest

from models.database import db
from models.user import User

# Skip entire module if MAIL_PASSWORD is not set
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
RECIPIENT_EMAIL = os.environ.get('TEST_RECIPIENT', 'DylanLee20@outlook.com')

pytestmark = pytest.mark.skipif(
    not MAIL_PASSWORD,
    reason='MAIL_PASSWORD env var not set — skipping live email test',
)


@pytest.fixture()
def live_app():
    """Flask app configured with REAL Outlook SMTP credentials."""
    # Must set env vars before Config is read
    os.environ['SECRET_KEY'] = 'live-email-test-secret'
    os.environ['ADMIN_PASSWORD'] = 'testadmin123'
    os.environ['DISABLE_SCHEDULER'] = 'true'
    os.environ['DATABASE_URL'] = 'sqlite://'

    from app import create_app
    flask_app, _scheduler = create_app()
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost:5000',
    })

    # Configure REAL Outlook SMTP
    from config import Config
    Config.MAIL_SERVER = 'smtp-mail.outlook.com'
    Config.MAIL_PORT = 587
    Config.MAIL_USE_TLS = True
    Config.MAIL_USERNAME = 'no_reply_newwhale@outlook.com'
    Config.MAIL_PASSWORD = MAIL_PASSWORD
    Config.MAIL_DEFAULT_SENDER = 'no_reply_newwhale@outlook.com'
    Config.SITE_URL = 'https://newwhaletech.com'

    with flask_app.app_context():
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.rollback()
        db.drop_all()


@pytest.fixture()
def live_client(live_app):
    return live_app.test_client()


class TestLiveEmail:
    """Sends REAL emails through Outlook SMTP."""

    def test_register_sends_real_verification_email(self, live_app, live_client):
        """
        Register a user and send a REAL verification email.

        After this test runs, check your inbox at the recipient address.
        """
        with live_app.app_context():
            print(f"\n{'=' * 60}")
            print(f"LIVE EMAIL TEST")
            print(f"{'=' * 60}")
            print(f"  SMTP Server:  smtp-mail.outlook.com:587")
            print(f"  From:         no_reply_newwhale@outlook.com")
            print(f"  To:           {RECIPIENT_EMAIL}")
            print(f"{'=' * 60}")

            # Register a user with the real recipient email
            print("\n  [1/4] Registering user...")
            resp = live_client.post('/auth/register', data={
                'username': 'live_test_user',
                'email': RECIPIENT_EMAIL,
                'password': 'securepass8',
                'confirm_password': 'securepass8',
            }, follow_redirects=True)

            assert resp.status_code == 200
            user = User.query.filter_by(username='live_test_user').first()
            assert user is not None
            assert user.email_verified is False
            print("  [1/4] User created (unverified)")

            # Check that a token was generated
            token = user.email_verification_token
            assert token is not None
            print(f"  [2/4] Verification token: {token[:20]}...")

            # The email was sent during registration
            verify_url = f"https://newwhaletech.com/auth/verify-email/{token}"
            print(f"  [3/4] Verification link: {verify_url}")

            # Verify using the token directly (simulating clicking the link)
            verify_path = f"/auth/verify-email/{token}"
            resp = live_client.get(verify_path, follow_redirects=True)
            assert resp.status_code == 200
            assert b'verified successfully' in resp.data.lower()

            user = User.query.filter_by(username='live_test_user').first()
            assert user.email_verified is True
            print("  [4/4] Token verified successfully in database")

            print(f"\n{'=' * 60}")
            print(f"  RESULT: PASS")
            print(f"")
            print(f"  CHECK YOUR INBOX at {RECIPIENT_EMAIL}")
            print(f"  (also check spam/junk folder)")
            print(f"  You should see an email from no_reply_newwhale@outlook.com")
            print(f"  Subject: 'Verify your NewWhale Career email address'")
            print(f"{'=' * 60}\n")
