"""Tests for free vs premium feature access controls."""

from datetime import datetime

import pytest

from models.resume import Resume
from models.user import User


def _login(client, username, password):
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=False)


@pytest.fixture()
def premium_verified_user(app, db):
    """Create and return a verified premium user."""
    with app.app_context():
        user = User(
            username='premiumuser',
            email='premium@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='premium',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username='premiumuser').first()


def test_application_tracker_remains_free(client, verified_user):
    """Free users should still access the job tracker dashboard."""
    _login(client, 'verifieduser', 'password123')

    resp = client.get('/dashboard')

    assert resp.status_code == 200


def test_free_user_can_access_resume_builder_page(client, verified_user):
    """Build-from-scratch page should be free-access for logged-in users."""
    _login(client, 'verifieduser', 'password123')

    resp = client.get('/resume/build')

    assert resp.status_code == 200


def test_free_user_can_access_resume_builder_api(client, verified_user):
    """Build-from-scratch API should not be paywalled."""
    _login(client, 'verifieduser', 'password123')

    resp = client.post('/resume/api/build', json={'full_name': 'Free User'})

    assert resp.status_code == 200


def test_free_user_blocked_from_polish_step(client, app, db, verified_user):
    """Polish/revision endpoint should remain paid."""
    with app.app_context():
        resume = Resume(
            user_id=verified_user.id,
            original_filename='resume.txt',
            stored_filename='resume.txt',
            file_path='',
            file_size=100,
            file_type='txt',
            extracted_text='Sample extracted resume content long enough for revision checks.',
            status='parsed',
        )
        db.session.add(resume)
        db.session.commit()
        resume_id = resume.id

    _login(client, 'verifieduser', 'password123')
    resp = client.post(f'/resume/{resume_id}/revise', json={})
    data = resp.get_json()

    assert resp.status_code == 403
    assert data['success'] is False
    assert 'subscription' in data['message'].lower()


def test_premium_user_can_access_resume_builder(client, premium_verified_user):
    """Premium users should still be able to open and call resume builder routes."""
    _login(client, 'premiumuser', 'password123')

    page = client.get('/resume/build')
    api = client.post('/resume/api/build', json={'full_name': 'Premium User'})
    api_data = api.get_json()

    assert page.status_code == 200
    assert api.status_code == 200
    assert 'requires a paid Premium subscription' not in (api_data.get('message') or '')


def test_free_user_blocked_from_cold_email(client, verified_user):
    """Cold email outreach should redirect free users to pricing."""
    _login(client, 'verifieduser', 'password123')

    resp = client.get('/outreach/', follow_redirects=False)

    assert resp.status_code == 302
    assert '/pricing' in resp.headers.get('Location', '')
