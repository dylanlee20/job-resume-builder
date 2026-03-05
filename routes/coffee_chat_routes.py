"""Coffee chat marketplace routes."""
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user

from models.database import db
from models.job import Job
from models.coffee_chat import (
    MentorProfile,
    MentorAvailability,
    CoffeeChatBooking,
    MentorshipNote,
    MeetingLink,
)
from services.coffee_chat_service import CoffeeChatService

coffee_chat_bp = Blueprint('coffee_chat', __name__, url_prefix='/coffee-chat')

TIMEZONE_CHOICES = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Los_Angeles',
    'Europe/London',
    'Asia/Hong_Kong',
    'Asia/Shanghai',
    'Australia/Sydney',
]

DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def _parse_utc_datetime(raw_value):
    """Parse ISO datetime into UTC-naive datetime."""
    value = (raw_value or '').strip()
    if not value:
        raise ValueError('Missing datetime.')

    normalized = value.replace('Z', '+00:00')
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@coffee_chat_bp.route('/')
@login_required
def mentors():
    """Mentor marketplace listing."""
    industry = (request.args.get('industry') or '').strip()
    role = (request.args.get('role') or '').strip()

    mentor_rows = CoffeeChatService.list_mentors(industry=industry or None, role=role or None)
    all_mentors = CoffeeChatService.list_mentors()
    industries = sorted({m.industry for m in all_mentors if m.industry})
    roles = sorted({m.role for m in all_mentors if m.role})

    return render_template(
        'coffee_chat/mentors.html',
        mentors=mentor_rows,
        industries=industries,
        roles=roles,
        selected_industry=industry,
        selected_role=role,
    )


@coffee_chat_bp.route('/mentor/onboard', methods=['GET', 'POST'])
@login_required
def mentor_onboard():
    """Create or update mentor profile and compliance declarations."""
    mentor = MentorProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        payload = {
            'name': request.form.get('name'),
            'headline': request.form.get('headline'),
            'industry': request.form.get('industry'),
            'role': request.form.get('role'),
            'company': request.form.get('company'),
            'years_experience': request.form.get('years_experience', type=int),
            'timezone': request.form.get('timezone'),
            'hourly_rate': request.form.get('hourly_rate', type=int),
            'coffee_chat_price': request.form.get('coffee_chat_price', type=int),
            'bio': request.form.get('bio'),
            'linkedin_url': request.form.get('linkedin_url'),
            'profile_photo': request.form.get('profile_photo'),
            'compliance_accepted': request.form.get('compliance_accepted') == '1',
            'employer_policy_confirmed': request.form.get('employer_policy_confirmed') == '1',
            'confidentiality_confirmed': request.form.get('confidentiality_confirmed') == '1',
        }

        missing = []
        for key in ('industry', 'role', 'timezone', 'coffee_chat_price'):
            if not payload.get(key):
                missing.append(key.replace('_', ' '))
        if missing:
            flash(f'Please fill required fields: {", ".join(missing)}.', 'error')
            return redirect(url_for('coffee_chat.mentor_onboard'))

        if not (
            payload['compliance_accepted']
            and payload['employer_policy_confirmed']
            and payload['confidentiality_confirmed']
        ):
            flash(
                'To list mentorship services, you must accept all compliance declarations '
                '(career guidance only, confidentiality, and employer policy).',
                'error',
            )
            return redirect(url_for('coffee_chat.mentor_onboard'))

        mentor = CoffeeChatService.upsert_mentor_profile(current_user, payload)

        # Replace recurring availability rows from submitted arrays.
        days = request.form.getlist('avail_day')
        starts = request.form.getlist('avail_start')
        ends = request.form.getlist('avail_end')
        windows = []
        for day, start_time, end_time in zip(days, starts, ends):
            if not start_time or not end_time:
                continue
            windows.append({
                'day_of_week': int(day),
                'start_time': start_time,
                'end_time': end_time,
            })

        if windows:
            CoffeeChatService.replace_availability(mentor.id, windows)

        flash('Mentor profile saved. You can now receive paid coffee chat bookings.', 'success')
        return redirect(url_for('coffee_chat.mentor_dashboard'))

    availabilities = []
    if mentor:
        availabilities = mentor.availabilities.order_by(
            MentorAvailability.day_of_week.asc(),
            MentorAvailability.start_time.asc(),
        ).all()

    return render_template(
        'coffee_chat/mentor_onboard.html',
        mentor=mentor,
        availabilities=availabilities,
        timezone_choices=TIMEZONE_CHOICES,
        day_labels=DAY_LABELS,
    )


@coffee_chat_bp.route('/mentor/dashboard')
@login_required
def mentor_dashboard():
    """Mentor management dashboard: sessions, earnings, and availability."""
    mentor = MentorProfile.query.filter_by(user_id=current_user.id).first()
    if not mentor:
        flash('Set up your mentor profile first.', 'warning')
        return redirect(url_for('coffee_chat.mentor_onboard'))

    CoffeeChatService.send_due_reminders(window_hours=24)

    upcoming = CoffeeChatBooking.query.filter(
        CoffeeChatBooking.mentor_id == mentor.id,
        CoffeeChatBooking.status.in_(['pending', 'confirmed']),
    ).order_by(CoffeeChatBooking.start_time.asc()).all()

    past = CoffeeChatBooking.query.filter(
        CoffeeChatBooking.mentor_id == mentor.id,
        CoffeeChatBooking.status.in_(['completed', 'cancelled']),
    ).order_by(CoffeeChatBooking.start_time.desc()).limit(50).all()

    successful = CoffeeChatBooking.query.filter(
        CoffeeChatBooking.mentor_id == mentor.id,
        CoffeeChatBooking.status.in_(['confirmed', 'completed']),
    ).all()
    gross_cents = sum(item.price_cents for item in successful if item.payment and item.payment.status == 'succeeded')
    payout_cents = sum(item.mentor_payout_cents for item in successful if item.payment and item.payment.status == 'succeeded')

    availabilities = mentor.availabilities.order_by(
        MentorAvailability.day_of_week.asc(),
        MentorAvailability.start_time.asc(),
    ).all()

    return render_template(
        'coffee_chat/mentor_dashboard.html',
        mentor=mentor,
        upcoming=upcoming,
        past=past,
        availabilities=availabilities,
        day_labels=DAY_LABELS,
        gross_cents=gross_cents,
        payout_cents=payout_cents,
    )


@coffee_chat_bp.route('/mentor/availability/add', methods=['POST'])
@login_required
def add_availability():
    """Add one recurring availability row."""
    mentor = MentorProfile.query.filter_by(user_id=current_user.id).first()
    if not mentor:
        flash('Set up your mentor profile first.', 'error')
        return redirect(url_for('coffee_chat.mentor_onboard'))

    try:
        CoffeeChatService.add_availability(
            mentor.id,
            day_of_week=request.form.get('day_of_week', type=int),
            start_time=request.form.get('start_time', ''),
            end_time=request.form.get('end_time', ''),
        )
        flash('Availability added.', 'success')
    except Exception as exc:
        flash(f'Could not add availability: {exc}', 'error')

    return redirect(url_for('coffee_chat.mentor_dashboard'))


@coffee_chat_bp.route('/mentor/availability/<int:availability_id>/delete', methods=['POST'])
@login_required
def delete_availability(availability_id):
    """Delete one recurring availability row."""
    mentor = MentorProfile.query.filter_by(user_id=current_user.id).first()
    if not mentor:
        flash('Set up your mentor profile first.', 'error')
        return redirect(url_for('coffee_chat.mentor_onboard'))

    try:
        CoffeeChatService.delete_availability(mentor.id, availability_id)
        flash('Availability removed.', 'info')
    except Exception as exc:
        flash(f'Could not remove availability: {exc}', 'error')

    return redirect(url_for('coffee_chat.mentor_dashboard'))


@coffee_chat_bp.route('/mentors/<int:mentor_id>')
@login_required
def mentor_profile(mentor_id):
    """Public mentor detail page with bookable slots."""
    mentor = MentorProfile.query.get_or_404(mentor_id)
    if not mentor.is_listable and mentor.user_id != current_user.id:
        abort(404)

    viewer_timezone = (request.args.get('tz') or 'UTC').strip()
    slots = CoffeeChatService.generate_slots(mentor, viewer_timezone=viewer_timezone, days_ahead=14)

    return render_template(
        'coffee_chat/mentor_profile.html',
        mentor=mentor,
        slots=slots,
        viewer_timezone=viewer_timezone,
        timezone_choices=TIMEZONE_CHOICES,
        liability_notice=(
            'The platform does not provide financial advice and is not responsible '
            'for statements made during mentorship sessions.'
        ),
    )


@coffee_chat_bp.route('/mentors/<int:mentor_id>/slots')
@login_required
def mentor_slots(mentor_id):
    """JSON slot endpoint for dynamic UI refresh."""
    mentor = MentorProfile.query.get_or_404(mentor_id)
    if not mentor.is_listable and mentor.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Mentor not available'}), 404

    viewer_timezone = (request.args.get('tz') or 'UTC').strip()
    slots = CoffeeChatService.generate_slots(mentor, viewer_timezone=viewer_timezone, days_ahead=14)
    return jsonify({'success': True, 'slots': slots})


@coffee_chat_bp.route('/bookings/create', methods=['POST'])
@login_required
def create_booking():
    """Create pending booking and redirect student to Stripe checkout."""
    mentor_id = request.form.get('mentor_id', type=int)
    student_timezone = (request.form.get('student_timezone') or 'UTC').strip()
    disclaimer_accepted = request.form.get('career_disclaimer') == '1'
    liability_notice_seen = request.form.get('liability_notice') == '1'

    try:
        start_utc = _parse_utc_datetime(request.form.get('start_utc'))
        end_utc = _parse_utc_datetime(request.form.get('end_utc'))
    except Exception as exc:
        flash(f'Invalid slot timestamp: {exc}', 'error')
        return redirect(url_for('coffee_chat.mentors'))

    success_template = (
        url_for('coffee_chat.booking_success', booking_id=0, _external=True).replace('/0', '/{booking_id}')
        + '?session_id={CHECKOUT_SESSION_ID}'
    )
    cancel_template = (
        url_for('coffee_chat.booking_cancel', booking_id=0, _external=True).replace('/0', '/{booking_id}')
    )

    try:
        booking, _payment, session = CoffeeChatService.create_checkout_booking(
            student=current_user,
            mentor_id=mentor_id,
            start_time_utc=start_utc,
            end_time_utc=end_utc,
            student_timezone=student_timezone,
            disclaimer_accepted=disclaimer_accepted,
            liability_notice_seen=liability_notice_seen,
            success_url=success_template,
            cancel_url=cancel_template,
        )
    except Exception as exc:
        flash(f'Could not create booking: {exc}', 'error')
        if mentor_id:
            return redirect(url_for('coffee_chat.mentor_profile', mentor_id=mentor_id))
        return redirect(url_for('coffee_chat.mentors'))

    response_format = (request.content_type or '').lower()
    if 'application/json' in response_format:
        return jsonify({
            'success': True,
            'booking_id': booking.id,
            'checkout_url': session.url,
        })

    return redirect(session.url)


@coffee_chat_bp.route('/bookings/<int:booking_id>/success')
@login_required
def booking_success(booking_id):
    """Post-checkout page while webhook finalizes confirmation."""
    booking = CoffeeChatBooking.query.get_or_404(booking_id)
    if current_user.id not in (booking.student_id, booking.mentor.user_id):
        abort(403)

    return render_template('coffee_chat/booking_status.html', booking=booking, status='success')


@coffee_chat_bp.route('/bookings/<int:booking_id>/cancel')
@login_required
def booking_cancel(booking_id):
    """Checkout cancellation page."""
    booking = CoffeeChatBooking.query.get_or_404(booking_id)
    if current_user.id != booking.student_id:
        abort(403)

    if booking.status == 'pending' and booking.payment and booking.payment.status == 'pending':
        booking.status = 'cancelled'
        booking.cancelled_at = CoffeeChatService.utcnow()
        booking.payment.status = 'failed'
        db.session.commit()

    return render_template('coffee_chat/booking_status.html', booking=booking, status='cancel')


@coffee_chat_bp.route('/bookings/<int:booking_id>/complete', methods=['POST'])
@login_required
def mark_booking_complete(booking_id):
    """Mentor marks a confirmed session as completed."""
    booking = CoffeeChatBooking.query.get_or_404(booking_id)
    if booking.mentor.user_id != current_user.id:
        abort(403)

    try:
        CoffeeChatService.complete_booking(booking)
        flash('Session marked as completed.', 'success')
    except Exception as exc:
        flash(f'Could not mark completed: {exc}', 'error')
    return redirect(url_for('coffee_chat.mentor_dashboard'))


@coffee_chat_bp.route('/student/dashboard')
@login_required
def student_dashboard():
    """Student dashboard for upcoming/past coffee chats + notes."""
    CoffeeChatService.send_due_reminders(window_hours=24)

    upcoming = CoffeeChatBooking.query.filter(
        CoffeeChatBooking.student_id == current_user.id,
        CoffeeChatBooking.status.in_(['pending', 'confirmed']),
    ).order_by(CoffeeChatBooking.start_time.asc()).all()

    past = CoffeeChatBooking.query.filter(
        CoffeeChatBooking.student_id == current_user.id,
        CoffeeChatBooking.status.in_(['completed', 'cancelled']),
    ).order_by(CoffeeChatBooking.start_time.desc()).limit(100).all()

    notes = MentorshipNote.query.filter_by(student_id=current_user.id).order_by(MentorshipNote.created_at.desc()).all()
    jobs = Job.query.order_by(Job.first_seen.desc()).limit(200).all()

    return render_template(
        'coffee_chat/student_dashboard.html',
        upcoming=upcoming,
        past=past,
        notes=notes,
        jobs=jobs,
    )


@coffee_chat_bp.route('/bookings/<int:booking_id>/notes', methods=['POST'])
@login_required
def save_booking_notes(booking_id):
    """Save post-chat notes + next steps tied to a session."""
    booking = CoffeeChatBooking.query.get_or_404(booking_id)
    if booking.student_id != current_user.id:
        abort(403)

    try:
        note = CoffeeChatService.save_student_note(
            booking=booking,
            student=current_user,
            notes=request.form.get('notes', ''),
            advice_received=request.form.get('advice_received', ''),
            next_steps=request.form.get('next_steps', ''),
            job_id=request.form.get('job_id', type=int),
        )
        flash('Session notes saved and linked to your mentorship history.', 'success')
        if request.is_json:
            return jsonify({'success': True, 'note': note.to_dict()})
    except Exception as exc:
        if request.is_json:
            return jsonify({'success': False, 'message': str(exc)}), 400
        flash(f'Could not save notes: {exc}', 'error')
    return redirect(url_for('coffee_chat.student_dashboard'))


@coffee_chat_bp.route('/meet/<token>')
@login_required
def meeting_room(token):
    """Internal meeting link landing page (privacy-safe default)."""
    link = MeetingLink.query.filter_by(meeting_token=token).first_or_404()
    booking = link.booking
    mentor_user_id = booking.mentor.user_id

    if current_user.id not in (booking.student_id, mentor_user_id):
        abort(403)

    if booking.status not in ('confirmed', 'completed'):
        flash('This session is not currently active.', 'warning')
        return redirect(url_for('coffee_chat.student_dashboard'))

    return render_template(
        'coffee_chat/meeting_room.html',
        booking=booking,
        meeting_link=link,
    )
