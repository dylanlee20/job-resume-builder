"""Authentication routes: register, login, logout, email verification."""
import logging
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify,
)
from flask_login import login_user, logout_user, login_required, current_user

from config import Config
from models.database import db
from models.user import User
from models.email_verification_token import EmailVerificationToken
from services.email_service import EmailService
from utils.rate_limiter import register_limiter, resend_limiter

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_verify_url(raw_token: str) -> str:
    """Build the full verification URL for an email link."""
    base = Config.APP_BASE_URL.rstrip('/')
    return f"{base}/auth/verify-email?token={raw_token}"


def _send_verification(user: User) -> None:
    """Generate a new token and send the verification email.

    Commits the token to the DB before sending so the link is valid
    even if the email delivery fails.
    """
    raw_token = EmailVerificationToken.create_for_user(user.id)
    db.session.commit()

    verify_url = _build_verify_url(raw_token)
    ok, err = EmailService.send_verification_email(user.email, user.username, verify_url)
    if not ok:
        logger.error("Failed to send verification email for user_id=%s: %s", user.id, err)


# Generic message that does not reveal whether an email is registered
_GENERIC_REGISTER_MSG = 'If your details are valid, a verification email has been sent. Please check your inbox.'
_GENERIC_RESEND_MSG = (
    'If that email is registered and unverified, '
    'we have sent a new verification link. Please check your inbox (and spam folder).'
)


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with email verification."""
    if current_user.is_authenticated:
        return redirect(url_for('web.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # --- IP-based rate limiting ---
        client_ip = request.remote_addr or '0.0.0.0'
        if not register_limiter.is_allowed(client_ip):
            flash('Too many registration attempts. Please try again later.', 'danger')
            return render_template('auth/register.html', username=username, email=email)

        # --- Input validation ---
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html',
                                   username=username, email=email)

        # --- Uniqueness checks ---
        # Username: OK to reveal taken (usernames are public identifiers)
        if User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first():
            flash('That username is already taken.', 'danger')
            return render_template('auth/register.html', email=email)

        # Email: do NOT reveal whether it exists — use generic message
        if User.query.filter(
            db.func.lower(User.email) == email
        ).first():
            flash(_GENERIC_REGISTER_MSG, 'success')
            return redirect(url_for('auth.login'))

        # --- Create user (unverified) ---
        user = User(
            username=username,
            email=email,
            email_verified=False,
            tier='free',
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get user.id

        # Generate token and send email
        raw_token = EmailVerificationToken.create_for_user(user.id)
        db.session.commit()

        verify_url = _build_verify_url(raw_token)
        ok, err = EmailService.send_verification_email(user.email, user.username, verify_url)
        if not ok:
            logger.error("Verification email failed for user_id=%s: %s", user.id, err)

        flash(_GENERIC_REGISTER_MSG, 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login with email-verification gate."""
    if current_user.is_authenticated:
        return redirect(url_for('web.index'))

    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'

        # Support login by username OR email
        user = (
            User.query.filter(
                db.func.lower(User.username) == identifier.lower()
            ).first()
            or
            User.query.filter(
                db.func.lower(User.email) == identifier.lower()
            ).first()
        )

        if not user or not user.check_password(password):
            flash('Invalid username/email or password.', 'danger')
            return render_template('auth/login.html', username=identifier)

        # Email verification gate (skip for admins)
        if user.needs_email_verification():
            flash(
                'Please verify your email address before logging in. '
                '<a href="' + url_for('auth.resend_verification') + '?email=' + user.email + '">'
                'Resend verification email</a>',
                'warning',
            )
            return render_template('auth/login.html', username=identifier,
                                   show_resend=True, resend_email=user.email)

        login_user(user, remember=remember)
        user.record_login()
        db.session.commit()

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('web.index'))

    return render_template('auth/login.html')


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------------------------
# Email verification — GET /auth/verify-email?token=...
# ---------------------------------------------------------------------------

@auth_bp.route('/verify-email')
def verify_email():
    """Handle the email verification link (query-param based)."""
    raw_token = request.args.get('token', '').strip()

    if not raw_token:
        flash('Missing verification token.', 'warning')
        return redirect(url_for('auth.login'))

    token_record = EmailVerificationToken.verify(raw_token)

    if token_record is None:
        flash(
            'This verification link is invalid, expired, or has already been used. '
            '<a href="' + url_for('auth.resend_verification') + '">Request a new one.</a>',
            'danger',
        )
        return redirect(url_for('auth.login'))

    user = User.query.get(token_record.user_id)
    if user is None:
        flash('Account not found.', 'danger')
        return redirect(url_for('auth.login'))

    if user.email_verified:
        flash('Your email is already verified. Please log in.', 'info')
        return redirect(url_for('auth.login'))

    # Mark token as used and user as verified
    token_record.used_at = datetime.utcnow()
    user.mark_email_verified()
    db.session.commit()

    flash('Email verified successfully! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------------------------
# Resend verification — POST /auth/resend-verification
# ---------------------------------------------------------------------------

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Allow unverified users to request a new verification email."""
    if current_user.is_authenticated and current_user.email_verified:
        return redirect(url_for('web.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
    else:
        email = request.args.get('email', '').strip().lower()

    if not email:
        return render_template('auth/resend_verification.html')

    # Email-based rate limiting (60s cooldown enforced via 3 req / 5 min limiter)
    if not resend_limiter.is_allowed(email):
        flash('Please wait before requesting another verification email.', 'warning')
        return redirect(url_for('auth.login'))

    user = User.query.filter(
        db.func.lower(User.email) == email
    ).first()

    # Always show generic message to prevent email enumeration
    if not user or user.email_verified:
        flash(_GENERIC_RESEND_MSG, 'info')
        return redirect(url_for('auth.login'))

    # Check per-user cooldown: 60 seconds since last token creation
    latest_token = (
        EmailVerificationToken.query
        .filter_by(user_id=user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    if latest_token:
        age = datetime.utcnow() - latest_token.created_at
        if age < timedelta(seconds=60):
            flash('A verification email was sent very recently. Please wait a minute.', 'warning')
            return redirect(url_for('auth.login'))

    _send_verification(user)
    flash(_GENERIC_RESEND_MSG, 'info')
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------------------------
# Password change (authenticated)
# ---------------------------------------------------------------------------

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html')

        if len(new_pw) < 8:
            flash('New password must be at least 8 characters.', 'danger')
            return render_template('auth/change_password.html')

        if new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
            return render_template('auth/change_password.html')

        current_user.set_password(new_pw)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('web.index'))

    return render_template('auth/change_password.html')


# ---------------------------------------------------------------------------
# AJAX: check username / email availability
# ---------------------------------------------------------------------------

@auth_bp.route('/check-username')
def check_username():
    username = request.args.get('username', '').strip()
    if len(username) < 3:
        return jsonify({'available': False, 'message': 'Too short'})
    taken = User.query.filter(
        db.func.lower(User.username) == username.lower()
    ).first() is not None
    return jsonify({
        'available': not taken,
        'message': 'Username taken' if taken else 'Available',
    })


@auth_bp.route('/check-email')
def check_email():
    """Check email format only — does NOT reveal existence to prevent enumeration."""
    email = request.args.get('email', '').strip().lower()
    if '@' not in email:
        return jsonify({'available': False, 'message': 'Invalid email format'})
    return jsonify({'available': True, 'message': 'Valid email format'})
