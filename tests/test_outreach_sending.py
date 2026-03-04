"""Tests for YAMM-style SMTP outreach sending."""

from datetime import datetime

import pytest

from models.cold_email import EmailCampaign, EmailRecipient
from models.user import User


def _login(client, username='premiummail', password='password123'):
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=False)


@pytest.fixture()
def premium_mail_user(app, db):
    with app.app_context():
        user = User(
            username='premiummail',
            email='premiummail@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='premium',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username='premiummail').first()


def test_sender_settings_can_be_saved(client, app, premium_mail_user):
    _login(client)

    resp = client.post('/outreach/settings', data={
        'sender_email': 'me@example.com',
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': '587',
        'smtp_username': 'me@example.com',
        'smtp_password': 'app-password',
        'smtp_use_tls': '1',
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert '/outreach/settings' in resp.headers.get('Location', '')

    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        assert user.sender_email == 'me@example.com'
        assert user.smtp_host == 'smtp.gmail.com'
        assert user.smtp_port == 587
        assert user.smtp_username == 'me@example.com'
        assert user.smtp_password == 'app-password'
        assert user.smtp_use_tls is True


def test_send_campaign_marks_pending_recipients_sent(client, app, db, premium_mail_user, monkeypatch):
    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        user.sender_email = 'me@example.com'
        user.smtp_host = 'smtp.gmail.com'
        user.smtp_port = 587
        user.smtp_username = 'me@example.com'
        user.smtp_password = 'app-password'
        user.smtp_use_tls = True

        campaign = EmailCampaign(
            user_id=user.id,
            name='Test Campaign',
            subject_template='Hello {{first_name}}',
            body_template='Hi {{first_name}}',
            status='draft',
        )
        db.session.add(campaign)
        db.session.commit()

        recipient = EmailRecipient(
            campaign_id=campaign.id,
            email='target@example.com',
            name='Target Person',
            tracking_id='track123',
            status='pending',
        )
        db.session.add(recipient)
        db.session.commit()
        campaign_id = campaign.id
        recipient_id = recipient.id

    class _FakeSMTP:
        def quit(self):
            return None

        def sendmail(self, *_args, **_kwargs):
            return {}

    monkeypatch.setattr(
        'services.cold_email_service.ColdEmailService._open_smtp_connection',
        lambda _user: _FakeSMTP()
    )

    _login(client)
    resp = client.post(f'/outreach/campaign/{campaign_id}/send', data={}, follow_redirects=False)

    assert resp.status_code == 302
    assert f'/outreach/campaign/{campaign_id}' in resp.headers.get('Location', '')

    with app.app_context():
        recipient = EmailRecipient.query.get(recipient_id)
        campaign = EmailCampaign.query.get(campaign_id)
        assert recipient.status == 'sent'
        assert recipient.sent_at is not None
        assert campaign.total_sent == 1
