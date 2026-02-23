"""Authentication routes for NewWhale Career v2"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models.database import db
from models.user import User
from services.email_service import EmailService
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page — only verified users can sign in"""
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username_or_email).first()
        if not user:
            user = User.query.filter_by(email=username_or_email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been disabled. Contact admin.', 'error')
                return render_template('login.html')

            # Block unverified users (admins bypass)
            if not user.email_verified and not user.is_admin:
                flash(
                    'Please verify your email before signing in. '
                    'Check your inbox or <a href="'
                    + url_for('auth.resend_verification', email=user.email)
                    + '">resend the verification email</a>.',
                    'warning'
                )
                return render_template('login.html')

            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()

            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/') or next_page.startswith('//'):
                next_page = url_for('web.dashboard')
            return redirect(next_page)
        else:
            flash('Invalid username/email or password', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration — create account, send verification, show check-email page"""
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters')
        elif len(username) > 30:
            errors.append('Username must be 30 characters or less')
        elif not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            errors.append('Username can only contain letters, numbers, dots, hyphens, and underscores')
        elif User.query.filter_by(username=username).first():
            errors.append('Username already taken')

        if not validate_email(email):
            errors.append('Please enter a valid email address')
        elif User.query.filter_by(email=email).first():
            errors.append('This email is already registered. Try signing in instead.')

        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        elif password != confirm_password:
            errors.append('Passwords do not match')

        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            user = User(
                username=username,
                email=email,
                tier='free',
                email_verified=False
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Send verification email
            sent = EmailService.send_verification_email(user)

            if sent:
                flash('Account created! Check your email to verify.', 'success')
            else:
                flash(
                    'Account created but we could not send the verification email. '
                    'Please try resending it.',
                    'warning'
                )

            return redirect(url_for('auth.verification_pending', email=email))

    return render_template('register.html')


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email and redirect to login"""
    success, message, user = EmailService.verify_token(token)

    if success:
        flash('Email verified! You can now sign in.', 'success')
        return redirect(url_for('auth.login'))
    else:
        flash(message, 'error')
        if user and not user.email_verified:
            return redirect(url_for('auth.verification_pending', email=user.email))
        return redirect(url_for('auth.login'))


@auth_bp.route('/verification-pending')
def verification_pending():
    """Check-your-email page shown after registration"""
    email = request.args.get('email', '')
    return render_template('verification_pending.html', email=email)


@auth_bp.route('/resend-verification')
def resend_verification():
    """Resend verification email"""
    email = request.args.get('email', '').strip().lower()
    if not email:
        flash('No email address provided.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('If that email is registered, we sent a new verification link.', 'info')
        return redirect(url_for('auth.verification_pending', email=email))

    if user.email_verified:
        flash('Your email is already verified. You can sign in.', 'success')
        return redirect(url_for('auth.login'))

    can_send, wait_seconds = EmailService.can_resend(user)
    if not can_send:
        flash(f'Please wait {wait_seconds} seconds before requesting another email.', 'warning')
        return redirect(url_for('auth.verification_pending', email=email))

    sent = EmailService.send_verification_email(user)
    if sent:
        flash('Verification email resent! Check your inbox.', 'success')
    else:
        flash('Could not send verification email. Please try again later.', 'error')

    return redirect(url_for('auth.verification_pending', email=email))


@auth_bp.route('/api/check-username')
def check_username():
    """AJAX endpoint for real-time username validation"""
    username = request.args.get('username', '').strip()
    if len(username) < 3:
        return {'available': False, 'message': 'Too short (min 3 chars)'}
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        return {'available': False, 'message': 'Invalid characters'}
    if User.query.filter_by(username=username).first():
        return {'available': False, 'message': 'Already taken'}
    return {'available': True, 'message': 'Available'}


@auth_bp.route('/api/check-email')
def check_email():
    """AJAX endpoint for real-time email validation"""
    email = request.args.get('email', '').strip().lower()
    if not validate_email(email):
        return {'available': False, 'message': 'Invalid email'}
    if User.query.filter_by(email=email).first():
        return {'available': False, 'message': 'Already registered'}
    return {'available': True, 'message': 'Available'}


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'error')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('web.dashboard'))

    return render_template('change_password.html')
