"""Admin routes"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('web.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/users')
@admin_required
def users():
    """Admin user management (placeholder)"""
    return render_template('admin/users.html')
