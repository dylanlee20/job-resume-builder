"""Authentication routes: admin-issued accounts only.

Self-registration and email verification were retired. Accounts are
created by an admin via /admin/users; this blueprint only handles
login, logout, and password change.
"""
import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models.database import db
from models.user import User
from utils.rate_limiter import login_limiter

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _client_ip() -> str:
    """Real client IP behind Cloudflare/nginx (falls back to the socket peer)."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''


def _is_safe_next(target: str) -> bool:
    """Whether a login ``next`` target is a safe same-site redirect.

    Only same-site relative paths are allowed. A bare ``startswith('/')`` check
    is not enough: browsers treat ``//evil.com`` and ``/\\evil.com`` as
    protocol-relative URLs and navigate off-site, so those must be rejected to
    prevent an open redirect.
    """
    if not target or not target.startswith('/'):
        return False
    if target.startswith('//') or target.startswith('/\\'):
        return False
    if '\\' in target or '\x00' in target:
        return False
    return True


def _login_keys(identifier: str) -> list:
    """Rate-limit keys for a login attempt.

    Throttle by source IP only. Keying on the username as well would let an
    attacker lock a victim out of their own account from any IP (a targeted
    denial-of-service); per-IP keying still limits password guessing without
    that side effect.
    """
    return [f'ip:{_client_ip()}']


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('web.index'))

    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'

        # Throttle password guessing. Block if either the source IP or the
        # targeted username has already burned through its failed-attempt budget.
        keys = _login_keys(identifier)
        if any(login_limiter.is_blocked(k) for k in keys):
            logger.warning('Login rate-limited for %s (ip=%s)', identifier, _client_ip())
            flash('Too many failed login attempts. Please wait a few minutes and try again.',
                  'danger')
            return render_template('auth/login.html', username=identifier), 429

        user = (
            User.query.filter(db.func.lower(User.username) == identifier.lower()).first()
            or User.query.filter(db.func.lower(User.email) == identifier.lower()).first()
        )

        if not user or not user.check_password(password):
            for k in keys:
                login_limiter.record(k)
            flash('Invalid username/email or password.', 'danger')
            return render_template('auth/login.html', username=identifier)

        # Block frozen / disabled accounts (admins always pass).
        if not user.is_admin and not user.is_active_account:
            msg = ('Your account has been frozen. Contact an admin to reactivate.'
                   if user.status == 'frozen'
                   else 'Your account has been disabled.')
            flash(msg, 'warning')
            return render_template('auth/login.html', username=identifier)

        # Successful login: clear any accumulated failed-attempt counters.
        for k in keys:
            login_limiter.reset(k)

        login_user(user, remember=remember)
        user.record_login()
        db.session.commit()

        next_page = request.args.get('next')
        if _is_safe_next(next_page):
            return redirect(next_page)
        return _post_login_redirect()

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


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


def _post_login_redirect():
    """Send the user to a section they actually have access to."""
    # Mentors live in their portal; send them straight there.
    if current_user.is_mentor:
        return redirect(url_for('portal.home'))
    if current_user.is_admin or current_user.has_app('main'):
        return redirect(url_for('web.index'))
    if current_user.has_app('macro'):
        return redirect('/macro')
    if current_user.has_app('competitions'):
        return redirect('/competitions')
    # A student with no app access still has their session portal.
    if not current_user.is_admin:
        return redirect(url_for('portal.home'))
    return redirect(url_for('auth.no_access'))


def _app_code_for_path(path: str) -> str:
    """Map an incoming request path to an app code for permission checks."""
    if path.startswith('/macro'):
        return 'macro'
    if path.startswith('/competitions'):
        return 'competitions'
    return 'main'


@auth_bp.route('/check')
def check():
    """Endpoint nginx auth_request calls before serving /macro and /competitions.

    Returns:
      - 401 if the visitor is not logged in (nginx 302s them to /auth/login)
      - 403 if the visitor is logged in but lacks the app they're hitting
             (nginx 302s them to /no-access via error_page)
      - 200 if access is granted
    """
    if not current_user.is_authenticated:
        return '', 401
    if not (current_user.is_admin or current_user.is_active_account):
        return '', 401
    original = request.headers.get('X-Original-URI', '/')
    code = _app_code_for_path(original)
    if current_user.has_app(code):
        return '', 200
    return '', 403


@auth_bp.route('/no-access')
def no_access():
    """Friendly landing for users who hit a section they don’t have access to."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    apps = sorted(current_user.app_set) if not current_user.is_admin else list(current_user.APP_CODES)
    return render_template('auth/no_access.html', apps=apps), 403
