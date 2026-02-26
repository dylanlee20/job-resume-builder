"""Shared test fixtures for the job-resume-builder test suite."""
import os
import pytest

# Set test environment variables BEFORE importing Config
os.environ['SECRET_KEY'] = 'test-secret-key-not-for-production'
os.environ['ADMIN_PASSWORD'] = 'testadmin123'
os.environ['ADMIN_USERNAME'] = 'testadmin'
os.environ['DISABLE_SCHEDULER'] = 'true'
os.environ['APP_BASE_URL'] = 'http://localhost:5000'
os.environ['EMAIL_VERIFICATION_EXPIRY_MINUTES'] = '30'
# Force in-memory DB BEFORE create_app() reads it
os.environ['DATABASE_URL'] = 'sqlite://'

from app import create_app
from models.database import db as _db
from models.user import User
from models.email_verification_token import EmailVerificationToken
from utils.rate_limiter import register_limiter, resend_limiter


@pytest.fixture(scope='session')
def app():
    """Create a Flask app configured for testing (session-scoped)."""
    flask_app, _scheduler = create_app()
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })
    yield flask_app


@pytest.fixture(autouse=True)
def db(request, app):
    """Create fresh database tables for every test.

    Skipped for tests that define their own e2e_app fixture.
    """
    if 'e2e_app' in request.fixturenames:
        yield _db
        return

    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Reset shared rate limiters between tests to avoid interference."""
    register_limiter._store.clear()
    resend_limiter._store.clear()
    yield
    register_limiter._store.clear()
    resend_limiter._store.clear()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Flask CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture()
def sample_user(app, db):
    """Create and return a basic unverified user."""
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            email_verified=False,
            tier='free',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username='testuser').first()


@pytest.fixture()
def verified_user(app, db):
    """Create and return a verified user."""
    with app.app_context():
        from datetime import datetime
        user = User(
            username='verifieduser',
            email='verified@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='free',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username='verifieduser').first()


@pytest.fixture()
def admin_user(app, db):
    """Create and return an admin user (always verified)."""
    with app.app_context():
        from datetime import datetime
        user = User(
            username='admin_test',
            email='admin_test@example.com',
            is_admin=True,
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='premium',
        )
        user.set_password('adminpass123')
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username='admin_test').first()
