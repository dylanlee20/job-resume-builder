"""Coffee chat mentorship marketplace service layer."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import stripe

from config import Config
from models.database import db
from models.job import Job
from models.coffee_chat import (
    MentorProfile,
    MentorAvailability,
    CoffeeChatBooking,
    CoffeeChatPayment,
    MeetingLink,
    MentorshipNote,
)
from services.email_service import EmailService

logger = logging.getLogger(__name__)

stripe.api_key = Config.STRIPE_SECRET_KEY


class CoffeeChatService:
    """Domain service for mentor onboarding, booking, and session lifecycle."""

    SESSION_MINUTES = 30
    PLATFORM_FEE_BPS = 1500  # 15%

    @staticmethod
    def utcnow():
        return datetime.utcnow()

    @staticmethod
    def _tz(timezone_name):
        """Return a valid timezone object, falling back to UTC."""
        try:
            return ZoneInfo(timezone_name or 'UTC')
        except Exception:
            return ZoneInfo('UTC')

    @classmethod
    def _compute_fee_split(cls, amount_cents):
        """Return (platform_fee_cents, mentor_payout_cents)."""
        platform_fee = int(round(amount_cents * cls.PLATFORM_FEE_BPS / 10000))
        mentor_payout = max(0, amount_cents - platform_fee)
        return platform_fee, mentor_payout

    @staticmethod
    def upsert_mentor_profile(user, payload):
        """Create or update mentor profile."""
        mentor = MentorProfile.query.filter_by(user_id=user.id).first()
        if not mentor:
            mentor = MentorProfile(user_id=user.id)
            db.session.add(mentor)

        mentor.name = (payload.get('name') or user.username).strip()[:120]
        mentor.headline = (payload.get('headline') or '').strip()[:200]
        mentor.industry = (payload.get('industry') or '').strip()[:120]
        mentor.role = (payload.get('role') or '').strip()[:120]
        mentor.company = (payload.get('company') or '').strip()[:120]
        mentor.bio = (payload.get('bio') or '').strip()[:5000]
        mentor.linkedin_url = (payload.get('linkedin_url') or '').strip()[:255]
        mentor.profile_photo = (payload.get('profile_photo') or '').strip()[:500]
        mentor.timezone = (payload.get('timezone') or 'UTC').strip()[:64]

        years_experience = payload.get('years_experience') or 0
        coffee_chat_price = payload.get('coffee_chat_price') or 0
        hourly_rate = payload.get('hourly_rate')

        mentor.years_experience = max(0, int(years_experience))
        mentor.coffee_chat_price = max(100, int(coffee_chat_price))
        mentor.hourly_rate = int(hourly_rate) if hourly_rate not in (None, '') else None

        mentor.compliance_accepted = bool(payload.get('compliance_accepted'))
        mentor.employer_policy_confirmed = bool(payload.get('employer_policy_confirmed'))
        mentor.confidentiality_confirmed = bool(payload.get('confidentiality_confirmed'))

        # Self-attested mentors become listable; admins can later set verified manually.
        if mentor.compliance_accepted and mentor.employer_policy_confirmed and mentor.confidentiality_confirmed:
            mentor.verified_status = mentor.verified_status if mentor.verified_status == 'verified' else 'self_attested'
        else:
            mentor.verified_status = 'pending'

        db.session.commit()
        return mentor

    @staticmethod
    def replace_availability(mentor_id, windows):
        """Replace all recurring weekly availability rows for a mentor."""
        mentor = MentorProfile.query.get(mentor_id)
        if not mentor:
            raise ValueError('Mentor profile not found.')

        MentorAvailability.query.filter_by(mentor_id=mentor_id).delete()

        for window in windows:
            day_of_week = int(window['day_of_week'])
            start_time = datetime.strptime(window['start_time'], '%H:%M').time()
            end_time = datetime.strptime(window['end_time'], '%H:%M').time()
            if end_time <= start_time:
                continue

            db.session.add(MentorAvailability(
                mentor_id=mentor_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
            ))

        db.session.commit()

    @staticmethod
    def add_availability(mentor_id, day_of_week, start_time, end_time):
        """Append one availability window to a mentor."""
        mentor = MentorProfile.query.get(mentor_id)
        if not mentor:
            raise ValueError('Mentor profile not found.')

        row = MentorAvailability(
            mentor_id=mentor_id,
            day_of_week=int(day_of_week),
            start_time=datetime.strptime(start_time, '%H:%M').time(),
            end_time=datetime.strptime(end_time, '%H:%M').time(),
        )
        if row.end_time <= row.start_time:
            raise ValueError('End time must be after start time.')

        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def delete_availability(mentor_id, availability_id):
        """Delete one availability row owned by the mentor."""
        row = MentorAvailability.query.get(availability_id)
        if not row or row.mentor_id != mentor_id:
            raise ValueError('Availability not found.')
        db.session.delete(row)
        db.session.commit()

    @classmethod
    def list_mentors(cls, industry=None, role=None):
        """Fetch listable mentors with optional filters."""
        query = MentorProfile.query.filter(
            MentorProfile.compliance_accepted.is_(True),
            MentorProfile.employer_policy_confirmed.is_(True),
            MentorProfile.confidentiality_confirmed.is_(True),
            MentorProfile.verified_status.in_(['self_attested', 'verified']),
        )
        if industry:
            query = query.filter(MentorProfile.industry == industry)
        if role:
            query = query.filter(MentorProfile.role == role)
        return query.order_by(MentorProfile.created_at.desc()).all()

    @classmethod
    def _booking_overlaps(cls, mentor_id, start_utc_naive, end_utc_naive):
        """Return True if requested slot overlaps active booking for mentor."""
        overlap = CoffeeChatBooking.query.filter(
            CoffeeChatBooking.mentor_id == mentor_id,
            CoffeeChatBooking.status.in_(['pending', 'confirmed']),
            CoffeeChatBooking.start_time < end_utc_naive,
            CoffeeChatBooking.end_time > start_utc_naive,
        ).first()
        return overlap is not None

    @classmethod
    def _slot_matches_availability(cls, mentor, start_utc_naive, end_utc_naive):
        """Return True if slot falls within mentor weekly availability."""
        mentor_tz = cls._tz(mentor.timezone)
        start_local = start_utc_naive.replace(tzinfo=timezone.utc).astimezone(mentor_tz)
        end_local = end_utc_naive.replace(tzinfo=timezone.utc).astimezone(mentor_tz)

        if end_local <= start_local:
            return False

        duration = int((end_utc_naive - start_utc_naive).total_seconds() // 60)
        if duration != cls.SESSION_MINUTES:
            return False

        day = start_local.weekday()
        rows = MentorAvailability.query.filter_by(mentor_id=mentor.id, day_of_week=day).all()
        if not rows:
            return False

        for row in rows:
            if row.start_time <= start_local.time() and end_local.time() <= row.end_time:
                return True
        return False

    @classmethod
    def generate_slots(cls, mentor, viewer_timezone='UTC', days_ahead=14):
        """Generate available 30-min slots in viewer timezone."""
        if not mentor:
            return []

        mentor_tz = cls._tz(mentor.timezone)
        viewer_tz = cls._tz(viewer_timezone)
        now_utc = cls.utcnow().replace(tzinfo=timezone.utc)

        start_local_date = now_utc.astimezone(mentor_tz).date()
        end_local_date = start_local_date + timedelta(days=days_ahead)
        window_start_utc = datetime.combine(start_local_date, datetime.min.time(), mentor_tz).astimezone(timezone.utc).replace(tzinfo=None)
        window_end_utc = datetime.combine(end_local_date, datetime.min.time(), mentor_tz).astimezone(timezone.utc).replace(tzinfo=None)

        existing = CoffeeChatBooking.query.filter(
            CoffeeChatBooking.mentor_id == mentor.id,
            CoffeeChatBooking.status.in_(['pending', 'confirmed']),
            CoffeeChatBooking.start_time < window_end_utc,
            CoffeeChatBooking.end_time > window_start_utc,
        ).all()

        existing_ranges = [(row.start_time, row.end_time) for row in existing]
        slots = []
        interval = timedelta(minutes=cls.SESSION_MINUTES)
        availability_map = {}

        for row in mentor.availabilities:
            availability_map.setdefault(row.day_of_week, []).append(row)

        for offset in range(days_ahead):
            local_date = start_local_date + timedelta(days=offset)
            day_rows = availability_map.get(local_date.weekday(), [])
            if not day_rows:
                continue

            for row in day_rows:
                slot_start_local = datetime.combine(local_date, row.start_time, mentor_tz)
                day_end_local = datetime.combine(local_date, row.end_time, mentor_tz)

                while slot_start_local + interval <= day_end_local:
                    slot_end_local = slot_start_local + interval
                    slot_start_utc = slot_start_local.astimezone(timezone.utc)
                    slot_end_utc = slot_end_local.astimezone(timezone.utc)
                    slot_start_utc_naive = slot_start_utc.replace(tzinfo=None)
                    slot_end_utc_naive = slot_end_utc.replace(tzinfo=None)

                    if slot_start_utc <= now_utc + timedelta(minutes=15):
                        slot_start_local += interval
                        continue

                    if any(s < slot_end_utc_naive and e > slot_start_utc_naive for s, e in existing_ranges):
                        slot_start_local += interval
                        continue

                    start_viewer = slot_start_utc.astimezone(viewer_tz)
                    end_viewer = slot_end_utc.astimezone(viewer_tz)
                    slots.append({
                        'start_utc': slot_start_utc_naive.isoformat(),
                        'end_utc': slot_end_utc_naive.isoformat(),
                        'date_label': start_viewer.strftime('%a, %b %d'),
                        'time_label': f"{start_viewer.strftime('%H:%M')} - {end_viewer.strftime('%H:%M')}",
                        'viewer_timezone': str(viewer_tz),
                    })

                    slot_start_local += interval

        return slots

    @classmethod
    def create_checkout_booking(
        cls,
        student,
        mentor_id,
        start_time_utc,
        end_time_utc,
        student_timezone,
        disclaimer_accepted,
        liability_notice_seen,
        success_url,
        cancel_url,
    ):
        """Create pending booking + Stripe checkout session."""
        mentor = MentorProfile.query.get(mentor_id)
        if not mentor or not mentor.is_listable:
            raise ValueError('Mentor is not available for booking.')
        if mentor.user_id == student.id:
            raise ValueError('You cannot book your own mentorship slot.')
        if not disclaimer_accepted:
            raise ValueError('You must accept the career-guidance-only disclaimer to continue.')
        if not liability_notice_seen:
            raise ValueError('You must acknowledge the platform liability notice to continue.')

        if end_time_utc <= start_time_utc:
            raise ValueError('Invalid slot duration.')

        if not cls._slot_matches_availability(mentor, start_time_utc, end_time_utc):
            raise ValueError('Selected slot is outside mentor availability.')
        if cls._booking_overlaps(mentor.id, start_time_utc, end_time_utc):
            raise ValueError('Selected slot is no longer available.')

        amount_cents = int(mentor.coffee_chat_price)
        if amount_cents <= 0:
            raise ValueError('Mentor pricing is invalid.')

        if not Config.STRIPE_SECRET_KEY:
            raise ValueError('Stripe is not configured on this server.')

        platform_fee_cents, mentor_payout_cents = cls._compute_fee_split(amount_cents)
        booking = CoffeeChatBooking(
            mentor_id=mentor.id,
            student_id=student.id,
            start_time=start_time_utc,
            end_time=end_time_utc,
            mentor_timezone=mentor.timezone,
            student_timezone=student_timezone or 'UTC',
            status='pending',
            student_disclaimer_accepted=True,
            liability_notice_seen=True,
            price_cents=amount_cents,
            platform_fee_cents=platform_fee_cents,
            mentor_payout_cents=mentor_payout_cents,
            currency='usd',
        )
        db.session.add(booking)
        db.session.flush()

        payment = CoffeeChatPayment(
            booking_id=booking.id,
            amount_cents=amount_cents,
            platform_fee_cents=platform_fee_cents,
            mentor_payout_cents=mentor_payout_cents,
            currency='usd',
            status='pending',
        )
        db.session.add(payment)
        db.session.flush()

        success_url = success_url.replace('{booking_id}', str(booking.id))
        cancel_url = cancel_url.replace('{booking_id}', str(booking.id))

        try:
            session = stripe.checkout.Session.create(
                mode='payment',
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': amount_cents,
                        'product_data': {
                            'name': f'Coffee Chat with {mentor.name}',
                            'description': f'{cls.SESSION_MINUTES}-minute career mentorship session',
                        },
                    },
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'payment_type': 'coffee_chat',
                    'booking_id': str(booking.id),
                    'mentor_id': str(mentor.id),
                    'student_id': str(student.id),
                },
                client_reference_id=str(booking.id),
            )
        except Exception:
            db.session.rollback()
            raise

        payment.stripe_checkout_session_id = session.id
        db.session.commit()

        cls._send_booking_created_notifications(booking)
        return booking, payment, session

    @classmethod
    def _meeting_url_for_token(cls, token):
        base = (Config.APP_BASE_URL or '').rstrip('/') or 'http://localhost:5000'
        return f'{base}/coffee-chat/meet/{token}'

    @classmethod
    def ensure_meeting_link(cls, booking, provider='internal'):
        """Create a meeting link for a confirmed booking if missing."""
        if booking.meeting_link:
            return booking.meeting_link

        token = secrets.token_urlsafe(24)
        link = MeetingLink(
            booking_id=booking.id,
            provider=provider,
            meeting_token=token,
            meeting_url=cls._meeting_url_for_token(token),
        )
        db.session.add(link)
        return link

    @classmethod
    def handle_checkout_completed(cls, session_data):
        """Stripe webhook handler for checkout.session.completed."""
        metadata = (session_data or {}).get('metadata') or {}
        if metadata.get('payment_type') != 'coffee_chat':
            return None

        booking_id = metadata.get('booking_id')
        if not booking_id:
            logger.error('Coffee chat checkout missing booking_id metadata.')
            return None

        booking = CoffeeChatBooking.query.get(int(booking_id))
        if not booking:
            logger.error('Coffee chat booking not found for booking_id=%s', booking_id)
            return None

        payment = booking.payment
        if not payment:
            logger.error('Coffee chat payment row missing for booking_id=%s', booking.id)
            return None

        if payment.status == 'succeeded' and booking.status in ('confirmed', 'completed'):
            return booking

        payment.status = 'succeeded'
        payment.stripe_payment_intent_id = session_data.get('payment_intent')
        payment.stripe_checkout_session_id = payment.stripe_checkout_session_id or session_data.get('id')
        if session_data.get('amount_total'):
            payment.amount_cents = int(session_data['amount_total'])

        booking.status = 'confirmed'
        booking.confirmed_at = cls.utcnow()
        cls.ensure_meeting_link(booking)
        db.session.commit()

        cls._send_booking_confirmed_notifications(booking)
        return booking

    @classmethod
    def handle_checkout_expired(cls, session_data):
        """Mark pending booking payment as failed on checkout expiry."""
        metadata = (session_data or {}).get('metadata') or {}
        if metadata.get('payment_type') != 'coffee_chat':
            return None

        booking_id = metadata.get('booking_id')
        if not booking_id:
            return None
        booking = CoffeeChatBooking.query.get(int(booking_id))
        if not booking or not booking.payment:
            return None

        if booking.payment.status == 'pending':
            booking.payment.status = 'failed'
            booking.status = 'cancelled'
            booking.cancelled_at = cls.utcnow()
            db.session.commit()
        return booking

    @classmethod
    def complete_booking(cls, booking):
        """Mark a confirmed booking as completed."""
        if booking.status != 'confirmed':
            raise ValueError('Only confirmed bookings can be marked complete.')
        booking.status = 'completed'
        booking.completed_at = cls.utcnow()
        db.session.commit()
        return booking

    @classmethod
    def save_student_note(cls, booking, student, notes, advice_received, next_steps, job_id=None):
        """Persist post-session student notes and optional job linkage."""
        if booking.student_id != student.id:
            raise ValueError('Unauthorized booking access.')
        if booking.status not in ('confirmed', 'completed'):
            raise ValueError('Notes can only be saved for active or completed sessions.')

        job = None
        if job_id:
            job = Job.query.get(int(job_id))
            if not job:
                raise ValueError('Selected job was not found.')

        note = MentorshipNote(
            booking_id=booking.id,
            student_id=student.id,
            job_id=job.id if job else None,
            notes=(notes or '').strip(),
            advice_received=(advice_received or '').strip(),
            next_steps=(next_steps or '').strip(),
        )
        db.session.add(note)
        db.session.commit()
        return note

    @classmethod
    def send_due_reminders(cls, window_hours=24):
        """Send reminders for upcoming confirmed sessions."""
        now = cls.utcnow()
        cutoff = now + timedelta(hours=window_hours)
        bookings = CoffeeChatBooking.query.filter(
            CoffeeChatBooking.status == 'confirmed',
            CoffeeChatBooking.start_time >= now,
            CoffeeChatBooking.start_time <= cutoff,
            CoffeeChatBooking.reminder_sent_at.is_(None),
        ).all()

        sent = 0
        for booking in bookings:
            try:
                cls.ensure_meeting_link(booking)
                db.session.flush()
                cls._send_booking_reminder_notifications(booking)
                booking.reminder_sent_at = cls.utcnow()
                sent += 1
            except Exception as exc:
                logger.error('Failed sending reminder for booking=%s: %s', booking.id, exc)
        db.session.commit()
        return sent

    @classmethod
    def _format_booking_time(cls, booking, tz_name):
        tz = cls._tz(tz_name)
        start_local = booking.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
        end_local = booking.end_time.replace(tzinfo=timezone.utc).astimezone(tz)
        return f"{start_local.strftime('%a, %b %d %Y %H:%M')} - {end_local.strftime('%H:%M')} ({tz})"

    @classmethod
    def _send_booking_created_notifications(cls, booking):
        """Notify both parties that booking is created and pending payment."""
        mentor_user = booking.mentor.user
        student = booking.student
        schedule_for_mentor = cls._format_booking_time(booking, booking.mentor_timezone)
        schedule_for_student = cls._format_booking_time(booking, booking.student_timezone)

        EmailService.send_coffee_chat_booking_created(
            to_email=mentor_user.email,
            recipient_name=mentor_user.username,
            counterpart_name=student.username,
            schedule_text=schedule_for_mentor,
        )
        EmailService.send_coffee_chat_booking_created(
            to_email=student.email,
            recipient_name=student.username,
            counterpart_name=booking.mentor.name,
            schedule_text=schedule_for_student,
        )

    @classmethod
    def _send_booking_confirmed_notifications(cls, booking):
        """Notify both parties when payment succeeds and booking confirms."""
        mentor_user = booking.mentor.user
        student = booking.student
        meeting_url = booking.meeting_link.meeting_url if booking.meeting_link else ''

        EmailService.send_coffee_chat_booking_confirmed(
            to_email=mentor_user.email,
            recipient_name=mentor_user.username,
            counterpart_name=student.username,
            schedule_text=cls._format_booking_time(booking, booking.mentor_timezone),
            meeting_url=meeting_url,
        )
        EmailService.send_coffee_chat_booking_confirmed(
            to_email=student.email,
            recipient_name=student.username,
            counterpart_name=booking.mentor.name,
            schedule_text=cls._format_booking_time(booking, booking.student_timezone),
            meeting_url=meeting_url,
        )

    @classmethod
    def _send_booking_reminder_notifications(cls, booking):
        """Send session reminder emails to mentor and student."""
        mentor_user = booking.mentor.user
        student = booking.student
        meeting_url = booking.meeting_link.meeting_url if booking.meeting_link else ''

        EmailService.send_coffee_chat_session_reminder(
            to_email=mentor_user.email,
            recipient_name=mentor_user.username,
            counterpart_name=student.username,
            schedule_text=cls._format_booking_time(booking, booking.mentor_timezone),
            meeting_url=meeting_url,
        )
        EmailService.send_coffee_chat_session_reminder(
            to_email=student.email,
            recipient_name=student.username,
            counterpart_name=booking.mentor.name,
            schedule_text=cls._format_booking_time(booking, booking.student_timezone),
            meeting_url=meeting_url,
        )
