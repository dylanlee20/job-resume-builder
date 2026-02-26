"""Diagnostic test: trace what ACTUALLY happens during registration.

No mocking — runs real code paths and inspects every step.
"""
import sqlite3

from flask import get_flashed_messages
from models.database import db
from models.user import User
from models.email_verification_token import EmailVerificationToken


class TestRegistrationReality:
    """Trace exactly what happens when POST /auth/register is called."""

    def test_step_by_step_registration(self, app, client):
        """Walk through registration one step at a time and inspect state."""
        with app.app_context():
            # ---- BEFORE registration ----
            print("\n=== STEP 1: State BEFORE registration ===")
            users_before = User.query.all()
            tokens_before = EmailVerificationToken.query.all()
            print(f"  Users in DB: {len(users_before)}")
            print(f"  Tokens in DB: {len(tokens_before)}")

            # Check that the table actually exists in SQLite
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"  DB tables: {tables}")
            assert 'email_verification_tokens' in tables, \
                "FATAL: email_verification_tokens table does NOT exist!"

            # ---- PERFORM registration ----
            print("\n=== STEP 2: POST /auth/register ===")
            response = client.post('/auth/register', data={
                'username': 'debuguser',
                'email': 'debug@example.com',
                'password': 'password123',
                'confirm_password': 'password123',
            }, follow_redirects=False)

            print(f"  Response status: {response.status_code}")
            print(f"  Response Location header: {response.headers.get('Location')}")

            # ---- AFTER registration: check user ----
            print("\n=== STEP 3: User state AFTER registration ===")
            user = User.query.filter_by(username='debuguser').first()
            if user is None:
                print("  ERROR: User was NOT created in DB!")
                print("  This means registration crashed before db.session.commit()")
                # Check if it's a 500 error
                print(f"  Response data: {response.data[:500]}")
                assert False, "User not created — registration failed silently"
            else:
                print(f"  User created: id={user.id}")
                print(f"  email={user.email}")
                print(f"  email_verified={user.email_verified}")
                print(f"  email_verified_at={user.email_verified_at}")
                print(f"  is_admin={user.is_admin}")
                print(f"  needs_email_verification()={user.needs_email_verification()}")
                assert user.email_verified is False, \
                    f"BUG: User was created with email_verified={user.email_verified}!"
                assert user.needs_email_verification() is True, \
                    "BUG: needs_email_verification() returned False for unverified user!"

            # ---- AFTER registration: check token ----
            print("\n=== STEP 4: Token state AFTER registration ===")
            tokens = EmailVerificationToken.query.filter_by(user_id=user.id).all()
            print(f"  Tokens for user: {len(tokens)}")
            if len(tokens) == 0:
                print("  ERROR: No verification token was created!")
                print("  This means EmailVerificationToken.create_for_user() failed")
                assert False, "No token created during registration"
            else:
                token = tokens[0]
                print(f"  token_hash length: {len(token.token_hash)}")
                print(f"  expires_at: {token.expires_at}")
                print(f"  used_at: {token.used_at}")
                print(f"  created_at: {token.created_at}")

            # ---- Check flash message ----
            print("\n=== STEP 5: Flash message check ===")
            # Follow the redirect to see the flash message
            response2 = client.post('/auth/register', data={
                'username': 'debuguser2',
                'email': 'debug2@example.com',
                'password': 'password123',
                'confirm_password': 'password123',
            }, follow_redirects=True)
            page_text = response2.data.decode('utf-8')
            print(f"  Final page status: {response2.status_code}")

            if 'If your details are valid' in page_text:
                print("  CORRECT flash message found!")
            elif 'Registration successful' in page_text:
                print("  BUG: OLD flash message found! VPS is running old code!")
            else:
                # Print any alert messages in the page
                import re
                alerts = re.findall(r'class="alert[^"]*"[^>]*>(.*?)</div>', page_text, re.DOTALL)
                print(f"  Alerts found: {alerts[:3]}")

            # ---- Try to log in (should be BLOCKED) ----
            print("\n=== STEP 6: Try login with unverified user ===")
            login_resp = client.post('/auth/login', data={
                'username': 'debuguser',
                'password': 'password123',
            }, follow_redirects=True)
            login_text = login_resp.data.decode('utf-8')

            if 'Please verify your email' in login_text:
                print("  CORRECT: Login blocked — verification required")
            elif 'Invalid username' in login_text:
                print("  BUG: User not found or password wrong after registration")
            else:
                print(f"  Login response status: {login_resp.status_code}")
                # Check if we ended up on the dashboard (bad — means login succeeded)
                if 'logout' in login_text.lower() or 'dashboard' in login_text.lower():
                    print("  BUG: User logged in WITHOUT email verification!")
                else:
                    import re
                    alerts = re.findall(r'class="alert[^"]*"[^>]*>(.*?)</div>', login_text, re.DOTALL)
                    print(f"  Alerts: {alerts[:3]}")

            print("\n=== DIAGNOSIS COMPLETE ===")

    def test_email_service_behavior_without_api_key(self, app):
        """Test what EmailService does when RESEND_API_KEY is empty."""
        with app.app_context():
            from services.email_service import EmailService
            from config import Config

            print(f"\n=== EmailService config ===")
            print(f"  RESEND_API_KEY present: {bool(Config.RESEND_API_KEY)}")
            print(f"  RESEND_API_KEY value: {'(set)' if Config.RESEND_API_KEY else '(empty)'}")
            print(f"  FROM_EMAIL: {Config.FROM_EMAIL}")
            print(f"  APP_BASE_URL: {Config.APP_BASE_URL}")

            ok, err = EmailService.send_verification_email(
                'test@example.com', 'testuser', 'http://localhost:5000/auth/verify-email?token=fake'
            )
            print(f"  send result: ok={ok}, err={err}")

            if ok and not Config.RESEND_API_KEY:
                print("  NOTE: Dev mode — email 'sent' successfully (no real email)")
                print("  On VPS, RESEND_API_KEY must be set as env var for real emails")
