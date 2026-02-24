"""Authentication routes: register, login, logout, email verification."""
import logging
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

from models.database import db
from models.user import User
from services.email_service import EmailService

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send_verification(user: User) -> None:
    """Generate a fresh token and fire the verification email.

    Commits the token to the DB before sending so the link is always valid
    even if the email send fails.
    """
    token = user.generate_verification_token()
    db.session.commit()  # Persist token first
    ok, err = EmailService.send_verification_email(user.email, user.username, token)
    if not ok:
        logger.error("Failed to send verification email to %s: %s", user.email, err)


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

        # --- Basic validation ---
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
        if User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first():
            flash('That username is already taken.', 'danger')
            return render_template('auth/register.html', email=email)

        if User.query.filter(
            db.func.lower(User.email) == email
        ).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html', username=username)

        # --- Create user ---
        user = User(
            username=username,
            email=email,
            email_verified=False,
            tier='free',
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get user.id before sending email

        # Generate & persist token, then send email
        token = user.generate_verification_token()
        db.session.commit()

        ok, err = EmailService.send_verification_email(user.email, user.username, token)
        if not ok:
            logger.error("Verification email failed for %s: %s", email, err)
            # Don't block registration — user can resend later

        flash(
            'Account created! Please check your email to verify your address before logging in.',
            'success',
        )
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
                '<a href="' + url_for('auth.resend_verification') + '?email=' + user.email + '">Resend verification email</a>',
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
# Email verification
# ---------------------------------------------------------------------------

@auth_bp.route('/verify-email/<token>')
def verify_email(token: str):
    """Handle the email verification link."""
    # Find user by token
    user = User.query.filter_by(email_verification_token=token).first()

    if user is None:
        # Could be already verified (token cleared) — give a helpful message
        flash(
            'This verification link is invalid or has already been used. '
            'If you are already verified, please log in.',
            'warning',
        )
        return redirect(url_for('auth.login'))

    if user.email_verified:
        # Edge case: token still present but already verified
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.session.commit()
        flash('Your email is already verified. Please log in.', 'info')
        return redirect(url_for('auth.login'))

    success = user.verify_email_token(token)
    if not success:
        # Token is expired
        flash(
            'This verification link has expired. '
            '<a href="' + url_for('auth.resend_verification') + '?email=' + user.email + '">'
            'Click here to get a new one.</a>',
            'danger',
        )
        return redirect(url_for('auth.login'))

    db.session.commit()
    flash(
        'Email verified successfully! You can now log in.',
        'success',
    )
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------------------------
# Resend verification
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

    user = User.query.filter(
        db.func.lower(User.email) == email
    ).first()

    # Always show the same message to prevent email enumeration
    generic_msg = (
        'If that email is registered and unverified, '
        'we have sent a new verification link. Please check your inbox (and spam folder).'
    )

    if not user:
        flash(generic_msg, 'info')
        return redirect(url_for('auth.login'))

    if user.email_verified:
        flash('Your email is already verified. Please log in.', 'info')
        return redirect(url_for('auth.login'))

    # Rate-limit resends: don't re-send if sent less than 2 minutes ago
    from datetime import timedelta
    if (
        user.email_verification_sent_at
        and (datetime.utcnow() - user.email_verification_sent_at) < timedelta(minutes=2)
    ):
        flash(
            'A verification email was sent very recently. '
            'Please wait a couple of minutes before requesting another.',
            'warning',
        )
        return redirect(url_for('auth.login'))

    _send_verification(user)
    flash(generic_msg, 'info')
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
    email = request.args.get('email', '').strip().lower()
    if '@' not in email:
        return jsonify({'available': False, 'message': 'Invalid email'})
    taken = User.query.filter(
        db.func.lower(User.email) == email
    ).first() is not None
    return jsonify({
        'available': not taken,
        'message': 'Email already registered' if taken else 'Available',
    })
