"""Tests for YAMM-style SMTP outreach sending."""

from datetime import datetime
from types import SimpleNamespace
import socket

import pytest

from models.cold_email import EmailCampaign, EmailRecipient
from models.user import User
from services.cold_email_service import ColdEmailService


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


def test_open_smtp_connection_prefers_ipv4(monkeypatch):
    attempts = []

    class _FakeSMTP:
        def __init__(self, timeout=30):
            self.timeout = timeout

        def connect(self, host, port):
            attempts.append((host, port))
            return 220

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, _username, _password):
            return None

        def quit(self):
            return None

    def _fake_getaddrinfo(_host, _port, type=None):  # pylint: disable=redefined-builtin
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:db8::1', 587, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('74.125.140.108', 587)),
        ]

    monkeypatch.setattr('services.cold_email_service.socket.getaddrinfo', _fake_getaddrinfo)
    monkeypatch.setattr('services.cold_email_service.smtplib.SMTP', _FakeSMTP)

    user = SimpleNamespace(
        smtp_host='smtp.gmail.com',
        smtp_port=587,
        smtp_use_tls=True,
        smtp_username='me@example.com',
        smtp_password='app-password',
    )

    server = ColdEmailService._open_smtp_connection(user)
    assert isinstance(server, _FakeSMTP)
    assert attempts[0][0] == '74.125.140.108'


def test_sender_profile_network_unreachable_returns_actionable_error(app, db, premium_mail_user, monkeypatch):
    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        user.sender_email = 'me@example.com'
        user.smtp_host = 'smtp.gmail.com'
        user.smtp_port = 587
        user.smtp_username = 'me@example.com'
        user.smtp_password = 'app-password'
        user.smtp_use_tls = True
        db.session.commit()

    def _raise_network_error(_user):
        raise OSError(101, 'Network is unreachable')

    monkeypatch.setattr(
        'services.cold_email_service.ColdEmailService._open_smtp_connection',
        _raise_network_error
    )

    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        ok, err = ColdEmailService.test_sender_profile(user)

    assert ok is False
    assert 'Outbound network route to smtp.gmail.com:587 is unavailable' in err
