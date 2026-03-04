"""Tests for resume cache UX and revision persistence."""

from datetime import datetime

import pytest

from models.resume import Resume
from models.resume_revision import ResumeRevision
from models.user import User


def _login(client, username, password='password123'):
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=False)


@pytest.fixture()
def premium_cache_user(app, db):
    """Create and return a verified premium user for cache tests."""
    with app.app_context():
        user = User(
            username='premiumcache',
            email='premiumcache@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='premium',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username='premiumcache').first()


def test_resume_history_redirects_to_hub_cache(client, verified_user):
    """Legacy /resume/history should redirect to Resume Tools cache anchor."""
    _login(client, 'verifieduser')

    resp = client.get('/resume/history', follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers.get('Location', '')
    assert '/resume/' in location
    assert '#resume-cache' in location


def test_resume_hub_shows_unified_path_and_cache(client, verified_user):
    """Resume hub should render unified path copy and cache section."""
    _login(client, 'verifieduser')

    resp = client.get('/resume/')
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'Unified Resume Path' in body
    assert 'My Resumes Cache' in body


def test_revise_persists_cached_revision(client, app, db, premium_cache_user, monkeypatch):
    """Successful premium revision should be saved to resume_revisions cache."""
    with app.app_context():
        resume = Resume(
            user_id=premium_cache_user.id,
            original_filename='resume.txt',
            stored_filename='resume.txt',
            file_path='',
            file_size=1200,
            file_type='txt',
            extracted_text='Experienced analyst with strong valuation and modeling skills.' * 4,
            status='assessed',
        )
        db.session.add(resume)
        db.session.commit()
        resume_id = resume.id

    monkeypatch.setattr(
        'services.resume_builder_service.ResumeBuilderService.revise_resume',
        lambda *_args, **_kwargs: {
            'success': True,
            'revised_text': 'Improved resume text',
            'changes': '- Stronger action verbs',
        }
    )

    _login(client, 'premiumcache')
    resp = client.post(
        f'/resume/{resume_id}/revise',
        json={'target_industry': 'Investment Banking'},
        follow_redirects=False,
    )
    data = resp.get_json()

    assert resp.status_code == 200
    assert data['success'] is True
    assert data.get('revision_id')

    with app.app_context():
        revision = ResumeRevision.query.get(data['revision_id'])
        assert revision is not None
        assert revision.resume_id == resume_id
        assert revision.user_id == premium_cache_user.id
        assert revision.target_industry == 'Investment Banking'
        assert revision.revision_suggestions == 'Improved resume text'
