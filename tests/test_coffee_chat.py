"""Tests for coffee chat marketplace flows."""
from datetime import datetime, timedelta, time
from types import SimpleNamespace

import pytest

from models.database import db
from models.user import User
from models.coffee_chat import (
    MentorProfile,
    MentorAvailability,
    CoffeeChatBooking,
    CoffeeChatPayment,
    MeetingLink,
    MentorshipNote,
)
from services.coffee_chat_service import CoffeeChatService
import services.coffee_chat_service as coffee_chat_service_module


def _login(client, username, password='password123'):
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=False)


@pytest.fixture()
def mentor_and_student(app, db):
    with app.app_context():
        mentor_user = User(
            username='mentor_user',
            email='mentor@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='free',
        )
        mentor_user.set_password('password123')

        student_user = User(
            username='student_user',
            email='student@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='free',
        )
        student_user.set_password('password123')

        db.session.add_all([mentor_user, student_user])
        db.session.commit()

        mentor_profile = MentorProfile(
            user_id=mentor_user.id,
            name='Mentor One',
            headline='IB Associate',
            industry='Investment Banking',
            role='Associate',
            company='BankCo',
            years_experience=4,
            timezone='UTC',
            coffee_chat_price=3000,
            verified_status='self_attested',
            compliance_accepted=True,
            employer_policy_confirmed=True,
            confidentiality_confirmed=True,
        )
        db.session.add(mentor_profile)
        db.session.commit()

        return {
            'mentor_user_id': mentor_user.id,
            'student_user_id': student_user.id,
            'mentor_profile_id': mentor_profile.id,
        }


def test_mentor_onboarding_requires_compliance(client, app):
    with app.app_context():
        user = User(
            username='onboard_user',
            email='onboard@example.com',
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            tier='free',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, 'onboard_user')
    resp = client.post('/coffee-chat/mentor/onboard', data={
        'name': 'Onboard Mentor',
        'industry': 'Investment Banking',
        'role': 'Analyst',
        'timezone': 'UTC',
        'coffee_chat_price': '2500',
        # Missing compliance checkboxes on purpose
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        profile = MentorProfile.query.filter_by(user_id=user_id).first()
        assert profile is None


def test_slot_generation_excludes_existing_bookings(app, db, mentor_and_student, monkeypatch):
    fixed_now = datetime(2026, 3, 2, 10, 0, 0)  # Monday UTC
    monkeypatch.setattr(
        CoffeeChatService,
        'utcnow',
        staticmethod(lambda: fixed_now),
    )

    with app.app_context():
        mentor = MentorProfile.query.get(mentor_and_student['mentor_profile_id'])
        db.session.add(MentorAvailability(
            mentor_id=mentor.id,
            day_of_week=0,  # Monday
            start_time=time(11, 0),
            end_time=time(12, 0),
        ))
        db.session.commit()

        slots = CoffeeChatService.generate_slots(mentor, viewer_timezone='UTC', days_ahead=1)
        assert len(slots) == 2

        first_start = datetime.fromisoformat(slots[0]['start_utc'])
        first_end = datetime.fromisoformat(slots[0]['end_utc'])
        booking = CoffeeChatBooking(
            mentor_id=mentor.id,
            student_id=mentor_and_student['student_user_id'],
            start_time=first_start,
            end_time=first_end,
            mentor_timezone='UTC',
            student_timezone='UTC',
            status='confirmed',
            student_disclaimer_accepted=True,
            liability_notice_seen=True,
            price_cents=3000,
            platform_fee_cents=450,
            mentor_payout_cents=2550,
            currency='usd',
        )
        db.session.add(booking)
        db.session.commit()

        refreshed_slots = CoffeeChatService.generate_slots(mentor, viewer_timezone='UTC', days_ahead=1)
        assert len(refreshed_slots) == 1


def test_create_booking_requires_disclaimer_and_creates_checkout(app, db, mentor_and_student, monkeypatch):
    fixed_now = datetime(2026, 3, 2, 10, 0, 0)  # Monday UTC
    monkeypatch.setattr(
        CoffeeChatService,
        'utcnow',
        staticmethod(lambda: fixed_now),
    )
    monkeypatch.setattr('services.coffee_chat_service.Config.STRIPE_SECRET_KEY', 'sk_test_123')

    with app.app_context():
        mentor = MentorProfile.query.get(mentor_and_student['mentor_profile_id'])
        if not mentor.availabilities.count():
            db.session.add(MentorAvailability(
                mentor_id=mentor.id,
                day_of_week=0,
                start_time=time(11, 0),
                end_time=time(12, 0),
            ))
            db.session.commit()
        slot = CoffeeChatService.generate_slots(mentor, viewer_timezone='UTC', days_ahead=1)[0]

    class _FakeSession:
        id = 'cs_test_123'
        url = 'https://checkout.stripe.test/session'

    monkeypatch.setattr(
        coffee_chat_service_module.stripe,
        'checkout',
        SimpleNamespace(Session=SimpleNamespace(create=lambda **_kwargs: _FakeSession())),
        raising=False,
    )

    with app.app_context():
        student = User.query.get(mentor_and_student['student_user_id'])
        mentor = MentorProfile.query.get(mentor_and_student['mentor_profile_id'])
        start_utc = datetime.fromisoformat(slot['start_utc'])
        end_utc = datetime.fromisoformat(slot['end_utc'])

        with pytest.raises(ValueError):
            CoffeeChatService.create_checkout_booking(
                student=student,
                mentor_id=mentor.id,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                student_timezone='UTC',
                disclaimer_accepted=False,
                liability_notice_seen=True,
                success_url='https://example.com/bookings/{booking_id}/success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url='https://example.com/bookings/{booking_id}/cancel',
            )

        booking, payment, session = CoffeeChatService.create_checkout_booking(
            student=student,
            mentor_id=mentor.id,
            start_time_utc=start_utc,
            end_time_utc=end_utc,
            student_timezone='UTC',
            disclaimer_accepted=True,
            liability_notice_seen=True,
            success_url='https://example.com/bookings/{booking_id}/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://example.com/bookings/{booking_id}/cancel',
        )

        assert session.url == 'https://checkout.stripe.test/session'
        assert booking is not None
        assert booking.status == 'pending'
        assert payment is not None
        assert payment.status == 'pending'
        assert payment.stripe_checkout_session_id == 'cs_test_123'


def test_checkout_webhook_confirms_booking_and_creates_meeting_link(app, db, mentor_and_student):
    with app.app_context():
        mentor = MentorProfile.query.get(mentor_and_student['mentor_profile_id'])
        booking = CoffeeChatBooking(
            mentor_id=mentor.id,
            student_id=mentor_and_student['student_user_id'],
            start_time=datetime(2026, 3, 4, 15, 0, 0),
            end_time=datetime(2026, 3, 4, 15, 30, 0),
            mentor_timezone='UTC',
            student_timezone='UTC',
            status='pending',
            student_disclaimer_accepted=True,
            liability_notice_seen=True,
            price_cents=3000,
            platform_fee_cents=450,
            mentor_payout_cents=2550,
            currency='usd',
        )
        db.session.add(booking)
        db.session.flush()
        db.session.add(CoffeeChatPayment(
            booking_id=booking.id,
            stripe_checkout_session_id='cs_test_pending',
            amount_cents=3000,
            platform_fee_cents=450,
            mentor_payout_cents=2550,
            currency='usd',
            status='pending',
        ))
        db.session.commit()

        payload = {
            'id': 'cs_test_pending',
            'payment_intent': 'pi_123',
            'amount_total': 3000,
            'metadata': {
                'payment_type': 'coffee_chat',
                'booking_id': str(booking.id),
                'mentor_id': str(mentor.id),
                'student_id': str(mentor_and_student['student_user_id']),
            },
        }
        updated_booking = CoffeeChatService.handle_checkout_completed(payload)
        assert updated_booking is not None

        refreshed = CoffeeChatBooking.query.get(booking.id)
        assert refreshed.status == 'confirmed'
        assert refreshed.payment.status == 'succeeded'
        assert refreshed.payment.stripe_payment_intent_id == 'pi_123'
        assert refreshed.meeting_link is not None
        assert refreshed.meeting_link.meeting_url.endswith(refreshed.meeting_link.meeting_token)


def test_student_can_save_post_chat_notes(client, app, db, mentor_and_student):
    with app.app_context():
        mentor = MentorProfile.query.get(mentor_and_student['mentor_profile_id'])
        booking = CoffeeChatBooking(
            mentor_id=mentor.id,
            student_id=mentor_and_student['student_user_id'],
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow() - timedelta(days=1, minutes=-30),
            mentor_timezone='UTC',
            student_timezone='UTC',
            status='completed',
            student_disclaimer_accepted=True,
            liability_notice_seen=True,
            price_cents=3000,
            platform_fee_cents=450,
            mentor_payout_cents=2550,
            currency='usd',
        )
        db.session.add(booking)
        db.session.commit()
        booking_id = booking.id

    _login(client, 'student_user')
    resp = client.post(f'/coffee-chat/bookings/{booking_id}/notes', data={
        'notes': 'Discussed networking strategy.',
        'advice_received': 'Target alumni and boutique firms first.',
        'next_steps': 'Send 5 tailored outreach emails this week.',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        note = MentorshipNote.query.filter_by(booking_id=booking_id).first()
        assert note is not None
        assert 'networking strategy' in note.notes.lower()
