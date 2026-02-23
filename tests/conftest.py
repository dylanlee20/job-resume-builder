"""Shared test fixtures for the test suite"""
import os
import pytest

# Override env vars BEFORE importing app/config
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['ADMIN_PASSWORD'] = 'testadminpassword'
os.environ['MAIL_USERNAME'] = 'test@example.com'
os.environ['MAIL_PASSWORD'] = 'testpassword'
os.environ['SITE_URL'] = 'https://test.example.com'
os.environ['DISABLE_SCHEDULER'] = 'true'
os.environ['FLASK_DEBUG'] = 'false'
os.environ['FLASK_PORT'] = '5099'

from app import create_app
from models.database import db as _db


@pytest.fixture(scope='session')
def app():
    """Create application for testing (session-scoped)."""
    app, _scheduler = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'  # in-memory
    app.config['WTF_CSRF_ENABLED'] = False  # disable CSRF for tests
    app.config['SERVER_NAME'] = 'localhost'

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(autouse=True)
def db_session(app):
    """Provide a clean DB for every test (auto-used)."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
