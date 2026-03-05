"""Tests for YAMM-style outreach sending (SMTP + Gmail + Outlook OAuth)."""

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


def test_sender_profile_accepts_gmail_oauth_without_smtp(app, db, premium_mail_user):
    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        user.gmail_email = 'gmailuser@example.com'
        user.gmail_refresh_token = 'refresh-token'
        user.gmail_access_token = 'access-token'
        db.session.commit()

        error = ColdEmailService._validate_sender_profile(user)
        assert error is None


def test_sender_profile_accepts_outlook_oauth_without_smtp(app, db, premium_mail_user):
    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        user.outlook_email = 'outlookuser@example.com'
        user.outlook_refresh_token = 'refresh-token'
        user.outlook_access_token = 'access-token'
        db.session.commit()

        error = ColdEmailService._validate_sender_profile(user)
        assert error is None


def test_send_campaign_uses_gmail_when_connected(client, app, db, premium_mail_user, monkeypatch):
    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        user.sender_email = 'gmailuser@example.com'
        user.gmail_email = 'gmailuser@example.com'
        user.gmail_refresh_token = 'refresh-token'
        user.gmail_access_token = 'access-token'

        campaign = EmailCampaign(
            user_id=user.id,
            name='Gmail Campaign',
            subject_template='Hello {{first_name}}',
            body_template='Hi {{first_name}}',
            status='draft',
        )
        db.session.add(campaign)
        db.session.commit()

        recipient = EmailRecipient(
            campaign_id=campaign.id,
            email='target@gmail.com',
            name='Target Person',
            tracking_id='track-gmail',
            status='pending',
        )
        db.session.add(recipient)
        db.session.commit()
        campaign_id = campaign.id
        recipient_id = recipient.id

    calls = []

    def _fake_gmail_send(_user, _msg):
        calls.append(True)
        return {'id': 'gmail-message-id'}

    monkeypatch.setattr(
        'services.cold_email_service.GmailService.send_mime_message',
        _fake_gmail_send
    )

    _login(client)
    resp = client.post(f'/outreach/campaign/{campaign_id}/send', data={}, follow_redirects=False)

    assert resp.status_code == 302
    assert f'/outreach/campaign/{campaign_id}' in resp.headers.get('Location', '')
    assert len(calls) == 1

    with app.app_context():
        recipient = EmailRecipient.query.get(recipient_id)
        campaign = EmailCampaign.query.get(campaign_id)
        assert recipient.status == 'sent'
        assert campaign.total_sent == 1


def test_send_campaign_uses_outlook_when_connected(client, app, db, premium_mail_user, monkeypatch):
    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        user.sender_email = 'outlookuser@example.com'
        user.outlook_email = 'outlookuser@example.com'
        user.outlook_refresh_token = 'refresh-token'
        user.outlook_access_token = 'access-token'

        campaign = EmailCampaign(
            user_id=user.id,
            name='Outlook Campaign',
            subject_template='Hello {{first_name}}',
            body_template='Hi {{first_name}}',
            status='draft',
        )
        db.session.add(campaign)
        db.session.commit()

        recipient = EmailRecipient(
            campaign_id=campaign.id,
            email='target@outlook.com',
            name='Target Person',
            tracking_id='track-outlook',
            status='pending',
        )
        db.session.add(recipient)
        db.session.commit()
        campaign_id = campaign.id
        recipient_id = recipient.id

    calls = []

    def _fake_outlook_send(*_args, **_kwargs):
        calls.append(True)
        return {'id': 'outlook-message-id'}

    monkeypatch.setattr(
        'services.cold_email_service.OutlookService.send_email',
        _fake_outlook_send
    )

    _login(client)
    resp = client.post(f'/outreach/campaign/{campaign_id}/send', data={}, follow_redirects=False)

    assert resp.status_code == 302
    assert f'/outreach/campaign/{campaign_id}' in resp.headers.get('Location', '')
    assert len(calls) == 1

    with app.app_context():
        recipient = EmailRecipient.query.get(recipient_id)
        campaign = EmailCampaign.query.get(campaign_id)
        assert recipient.status == 'sent'
        assert campaign.total_sent == 1


def test_gmail_connect_starts_oauth_flow(client, premium_mail_user, monkeypatch):
    _login(client)
    monkeypatch.setattr('routes.outreach_routes.GmailService.is_configured', lambda: True)

    seen_states = []

    def _fake_auth_url(state):
        seen_states.append(state)
        return f'https://accounts.google.com/o/oauth2/v2/auth?state={state}'

    monkeypatch.setattr('routes.outreach_routes.GmailService.build_authorization_url', _fake_auth_url)

    resp = client.get('/outreach/gmail/connect', follow_redirects=False)
    assert resp.status_code == 302
    assert 'accounts.google.com' in resp.headers['Location']
    assert len(seen_states) == 1


def test_gmail_callback_saves_connected_account(client, app, db, premium_mail_user, monkeypatch):
    _login(client)
    with client.session_transaction() as sess:
        sess['gmail_oauth_state'] = 'state123'
        sess['gmail_oauth_user_id'] = premium_mail_user.id

    def _fake_connect(user, _code):
        user.gmail_email = 'gmailuser@example.com'
        user.gmail_refresh_token = 'refresh-token'
        user.gmail_access_token = 'access-token'
        db.session.commit()
        return user.gmail_email

    monkeypatch.setattr(
        'routes.outreach_routes.GmailService.connect_user_with_code',
        _fake_connect
    )

    resp = client.get('/outreach/gmail/callback?state=state123&code=abc', follow_redirects=False)
    assert resp.status_code == 302
    assert '/outreach/settings' in resp.headers.get('Location', '')

    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        assert user.gmail_email == 'gmailuser@example.com'
        assert user.gmail_refresh_token == 'refresh-token'


def test_outlook_connect_starts_oauth_flow(client, premium_mail_user, monkeypatch):
    _login(client)
    monkeypatch.setattr('routes.outreach_routes.OutlookService.is_configured', lambda: True)

    seen_states = []

    def _fake_auth_url(state):
        seen_states.append(state)
        return f'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state={state}'

    monkeypatch.setattr('routes.outreach_routes.OutlookService.build_authorization_url', _fake_auth_url)

    resp = client.get('/outreach/outlook/connect', follow_redirects=False)
    assert resp.status_code == 302
    assert 'login.microsoftonline.com' in resp.headers['Location']
    assert len(seen_states) == 1


def test_outlook_callback_saves_connected_account(client, app, db, premium_mail_user, monkeypatch):
    _login(client)
    with client.session_transaction() as sess:
        sess['outlook_oauth_state'] = 'state456'
        sess['outlook_oauth_user_id'] = premium_mail_user.id

    def _fake_connect(user, _code):
        user.outlook_email = 'outlookuser@example.com'
        user.outlook_refresh_token = 'refresh-token'
        user.outlook_access_token = 'access-token'
        db.session.commit()
        return user.outlook_email

    monkeypatch.setattr(
        'routes.outreach_routes.OutlookService.connect_user_with_code',
        _fake_connect
    )

    resp = client.get('/outreach/outlook/callback?state=state456&code=xyz', follow_redirects=False)
    assert resp.status_code == 302
    assert '/outreach/settings' in resp.headers.get('Location', '')

    with app.app_context():
        user = User.query.get(premium_mail_user.id)
        assert user.outlook_email == 'outlookuser@example.com'
        assert user.outlook_refresh_token == 'refresh-token'
