"""Authentication and authorization decorators"""
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def mentor_required(f):
    """Require a logged-in mentor account."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_mentor:
            flash('This area is for mentor accounts.', 'danger')
            return redirect(url_for('portal.home'))
        return f(*args, **kwargs)
    return decorated_function


def mentor_or_admin(f):
    """Allow a mentor or an admin (admin logs on behalf of a mentor)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not (current_user.is_mentor or current_user.is_admin):
            flash('This area is for mentor accounts.', 'danger')
            return redirect(url_for('portal.home'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """Require a logged-in student account (not mentor, not admin)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.is_admin or current_user.is_mentor:
            flash('This area is for student accounts.', 'danger')
            return redirect(url_for('portal.home'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin access for a route

    Usage:
        @app.route('/admin/dashboard')
        @login_required
        @admin_required
        def admin_dashboard():
            return render_template('admin_dashboard.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))

        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('web.dashboard'))

        return f(*args, **kwargs)
    return decorated_function
