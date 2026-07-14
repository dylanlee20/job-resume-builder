"""Security response headers applied to every HTTP response.

Registered once from the app factory. Headers are set with ``setdefault`` so a
route that has already chosen its own value (e.g. the watermarked-PNG stream in
routes/slides.py sets its own Cache-Control / nosniff) is never overridden.

The Content-Security-Policy allowlists exactly the external origins the site
loads today: jsDelivr (Bootstrap + icons), code.jquery.com (jQuery), and Google
Fonts. 'unsafe-inline' is required because templates carry inline styles and a
handful of inline event handlers; it can be tightened to nonces later without
touching this contract.
"""
from flask import request

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
    "img-src 'self' data: https:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)

STATIC_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    'Content-Security-Policy': CONTENT_SECURITY_POLICY,
}

HSTS_VALUE = 'max-age=31536000; includeSubDomains'


def _is_https() -> bool:
    """True when the visitor's connection is HTTPS.

    gunicorn sits behind nginx over plain HTTP, so request.is_secure is False in
    production; trust the proxy's X-Forwarded-Proto instead. Gating HSTS on this
    avoids pinning a local http:// dev host to HTTPS.
    """
    if request.is_secure:
        return True
    forwarded = request.headers.get('X-Forwarded-Proto', '')
    return forwarded.split(',')[0].strip().lower() == 'https'


def register_security_headers(app):
    """Attach the after_request hook that stamps security headers."""

    @app.after_request
    def _apply_security_headers(response):
        for header, value in STATIC_HEADERS.items():
            response.headers.setdefault(header, value)
        if _is_https():
            response.headers.setdefault('Strict-Transport-Security', HSTS_VALUE)
        return response

    return app
