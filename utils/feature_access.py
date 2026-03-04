"""Helpers for enforcing paid feature access consistently."""

from functools import wraps

from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user


def _wants_json_response() -> bool:
    """Return True when caller expects JSON rather than an HTML redirect."""
    if request.is_json:
        return True

    content_type = (request.content_type or '').lower()
    if 'application/json' in content_type:
        return True

    if request.path.startswith('/resume/api/'):
        return True

    accept = request.accept_mimetypes
    return accept.best == 'application/json' and accept['application/json'] > accept['text/html']


def require_premium_feature(feature_name: str):
    """Require a paid Premium subscription for a route."""
    message = f'{feature_name} requires a paid Premium subscription.'

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if current_user.is_authenticated and current_user.is_premium:
                return func(*args, **kwargs)

            if _wants_json_response():
                return jsonify({
                    'success': False,
                    'message': message,
                    'upgrade_url': url_for('web.pricing'),
                }), 403

            flash(message, 'warning')
            return redirect(url_for('web.pricing'))

        return wrapped

    return decorator
