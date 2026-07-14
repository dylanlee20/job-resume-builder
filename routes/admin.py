"""Admin routes for scraper monitoring and user management"""
from flask import (
    Blueprint, render_template, redirect, url_for, jsonify, flash, request,
    Response, abort,
)
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from models.database import db
from models.user import User, generate_portal_code
from models.scraper_run import ScraperRun
from models.session_record import SessionRecord, SESSION_TYPES
from models.question_bank import QuestionBankEntry
from models.mentor_rate import MentorRate
from models.student_payment import StudentPayment
from models.mentor_payout import MentorPayout
from models.job import Job
from services.job_service import JobService
from services.slides_service import render_watermarked_png, SECTION_TITLE_OVERRIDES
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta


def _curriculum_choices():
    """[(slug, display_title)] for the seven curriculum sections, in order."""
    return [(slug, SECTION_TITLE_OVERRIDES.get(slug, slug)) for slug in User.CURRICULUM_CODES]
from pathlib import Path
import os
import re
import secrets
import string
import sys
import subprocess

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Where uploaded question-bank images live (persists across deploys).
_QB_DIR = Path(__file__).resolve().parent.parent / 'uploads' / 'question_bank'
_QB_ALLOWED = {'.png', '.jpg', '.jpeg', '.webp'}


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('web.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*"


def _generate_password(length: int = 14) -> str:
    return ''.join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def _normalize_username(raw: str) -> str:
    return re.sub(r'\s+', '', (raw or '').strip())


@admin_bp.route('/users')
@admin_required
def users():
    """Admin user management — list all users."""
    all_users = User.query.order_by(User.created_at.desc()).all()
    # One-shot password from POST flow lives in the session via a flashed pair.
    issued_credentials = request.args.get('issued')
    issued_username = request.args.get('username')

    recent_sessions = (
        SessionRecord.query.order_by(SessionRecord.created_at.desc()).limit(30).all()
    )
    # Students to choose from when logging a session (named roster first).
    student_choices = sorted(
        [u for u in all_users if not u.is_admin],
        key=lambda u: (u.full_name or u.username).lower(),
    )

    return render_template(
        'admin/users.html',
        users=all_users,
        issued_credentials=issued_credentials,
        issued_username=issued_username,
        recent_sessions=recent_sessions,
        student_choices=student_choices,
        session_types=SESSION_TYPES,
        curriculum_choices=_curriculum_choices(),
    )


# ---- Question Bank ---------------------------------------------------------

@admin_bp.route('/question-bank')
@admin_required
def question_bank():
    """Admin question bank — list uploaded interview question images."""
    entries = QuestionBankEntry.query.order_by(QuestionBankEntry.created_at.desc()).all()
    return render_template('admin/question_bank.html', entries=entries)


@admin_bp.route('/question-bank/upload', methods=['POST'])
@admin_required
def question_bank_upload():
    """Upload a question-bank image."""
    title = (request.form.get('title', '') or '').strip()
    student = (request.form.get('student', '') or '').strip() or None
    program_round = (request.form.get('program_round', '') or '').strip() or None
    file = request.files.get('image')

    if not title:
        flash('A title is required.', 'danger')
        return redirect(url_for('admin.question_bank'))
    if not file or not file.filename:
        flash('Choose an image to upload.', 'danger')
        return redirect(url_for('admin.question_bank'))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _QB_ALLOWED:
        flash(f'Unsupported file type {ext}. Use PNG, JPG, or WEBP.', 'danger')
        return redirect(url_for('admin.question_bank'))

    _QB_DIR.mkdir(parents=True, exist_ok=True)
    stored = f"{secrets.token_hex(8)}{ext}"
    file.save(str(_QB_DIR / stored))

    db.session.add(QuestionBankEntry(
        title=title,
        student=student,
        program_round=program_round,
        original_filename=secure_filename(file.filename),
        stored_filename=stored,
        uploaded_by=current_user.username,
    ))
    db.session.commit()
    flash('Question bank image uploaded.', 'success')
    return redirect(url_for('admin.question_bank'))


@admin_bp.route('/question-bank/<int:entry_id>/image')
@admin_required
def question_bank_image(entry_id):
    """Serve a question-bank image watermarked with viewer email + IP + EST."""
    entry = QuestionBankEntry.query.get_or_404(entry_id)
    path = _QB_DIR / entry.stored_filename
    if not path.is_file():
        abort(404)
    png = render_watermarked_png(path, '', show_ip=False, show_email=False)
    return Response(png, mimetype='image/png')


@admin_bp.route('/question-bank/<int:entry_id>/delete', methods=['POST'])
@admin_required
def question_bank_delete(entry_id):
    """Delete a question-bank entry and its file."""
    entry = QuestionBankEntry.query.get_or_404(entry_id)
    try:
        (_QB_DIR / entry.stored_filename).unlink(missing_ok=True)
    except OSError:
        pass
    db.session.delete(entry)
    db.session.commit()
    flash('Question bank entry deleted.', 'success')
    return redirect(url_for('admin.question_bank'))


@admin_bp.route('/sessions/create', methods=['POST'])
@admin_required
def create_session():
    """Log a coaching/mentoring session from the Session History panel."""
    mentor_name = (request.form.get('mentor_name', '') or '').strip()
    session_type = (request.form.get('session_type', '') or '').strip()
    topic = (request.form.get('topic', '') or '').strip()
    feedback = (request.form.get('feedback', '') or '').strip()
    student_id_raw = (request.form.get('student_id', '') or '').strip()

    errors = []
    if not mentor_name:
        errors.append('Mentor name is required.')
    if session_type not in SESSION_TYPES:
        errors.append('Pick a valid session type.')

    rating = None
    rating_raw = (request.form.get('rating', '') or '').strip()
    if rating_raw:
        try:
            rating = int(rating_raw)
            if not 1 <= rating <= 5:
                raise ValueError
        except ValueError:
            errors.append('Rating must be between 1 and 5.')

    student_id = None
    if student_id_raw:
        try:
            student_id = int(student_id_raw)
            if not User.query.get(student_id):
                errors.append('Selected student no longer exists.')
                student_id = None
        except ValueError:
            errors.append('Invalid student.')

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('admin.users'))

    record = SessionRecord(
        student_id=student_id,
        mentor_name=mentor_name,
        session_type=session_type,
        topic=topic or None,
        rating=rating,
        feedback=feedback or None,
        status='approved',  # admin-logged sessions are trusted / count immediately
        approved_at=datetime.utcnow(),
    )
    db.session.add(record)
    db.session.commit()
    flash('Session logged.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    """Create a new account with an admin-generated password (shown once)."""
    username = _normalize_username(request.form.get('username', ''))
    email = (request.form.get('email', '') or '').strip().lower()
    make_admin = request.form.get('is_admin') == 'on'
    account_type = (request.form.get('account_type', 'student') or 'student').strip()
    is_mentor = account_type == 'mentor' and not make_admin
    explicit_password = (request.form.get('password', '') or '').strip()
    payout_currency = (request.form.get('payout_currency', 'USD') or 'USD').strip().upper()[:3] or 'USD'

    full_name = (request.form.get('full_name', '') or '').strip() or None
    college = (request.form.get('college', '') or '').strip() or None
    graduation_year = None
    grad_raw = (request.form.get('graduation_year', '') or '').strip()

    total_sessions = None
    total_raw = (request.form.get('total_sessions', '') or '').strip()

    exchange_rate = None
    fx_raw = (request.form.get('exchange_rate', '') or '').strip()

    errors = []
    if grad_raw:
        try:
            graduation_year = int(grad_raw)
            if not 1950 <= graduation_year <= 2100:
                raise ValueError
        except ValueError:
            errors.append('Graduation year must be a valid year.')
    if fx_raw:
        try:
            exchange_rate = Decimal(fx_raw)
            if exchange_rate <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            errors.append('Exchange rate must be a positive number.')
    if len(username) < 3:
        errors.append('Username must be at least 3 characters.')
    if email and ('@' not in email or len(email) < 5):
        errors.append('If you enter an email, it must be a valid one.')
    if explicit_password and len(explicit_password) < 8:
        errors.append('Custom password must be at least 8 characters.')
    if total_raw:
        try:
            total_sessions = int(total_raw)
            if total_sessions < 1:
                raise ValueError
        except ValueError:
            errors.append('Student package size must be a positive number.')
    if User.query.filter(db.func.lower(User.username) == username.lower()).first():
        errors.append(f"Username '{username}' is already taken.")
    if email and User.query.filter(db.func.lower(User.email) == email).first():
        errors.append(f"Email '{email}' is already in use.")

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('admin.users'))

    # Email is optional. When blank, store a unique placeholder (never emailed);
    # username uniqueness guarantees the placeholder is unique too.
    if not email:
        email = f"{username.lower()}@placeholder.local"

    password = explicit_password or _generate_password()
    user = User(
        username=username,
        email=email,
        is_admin=make_admin,
        is_mentor=is_mentor,
        status='active',
        email_verified=True,
        email_verified_at=datetime.utcnow(),
        portal_code=generate_portal_code(),
        payout_currency=payout_currency,
        total_sessions=total_sessions,
        exchange_rate=exchange_rate,
        full_name=full_name,
        college=college,
        graduation_year=graduation_year,
    )
    user.set_password(password)
    user.set_allowed_apps(request.form.getlist('allowed_apps'))
    if is_mentor:
        user.set_allowed_curriculums(request.form.getlist('allowed_curriculums'))
    db.session.add(user)
    # Retry once on the (very unlikely) portal_code unique-collision race.
    from sqlalchemy.exc import IntegrityError
    for _ in range(3):
        try:
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            user.portal_code = generate_portal_code()
            db.session.add(user)
    else:
        flash('Could not issue the account (ID collision). Please try again.', 'danger')
        return redirect(url_for('admin.users'))

    # Pass the one-shot password back via the URL so the admin can copy it
    # out of the page and share it with the user. After they navigate away
    # it's gone.
    return redirect(url_for('admin.users', issued=password, username=username))


def _set_status(user_id: int, new_status: str, label: str):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot change your own status.', 'danger')
        return redirect(url_for('admin.users'))
    user.status = new_status
    db.session.commit()
    flash(f"User '{user.username}' is now {label}.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/freeze', methods=['POST'])
@admin_required
def freeze_user(user_id):
    return _set_status(user_id, 'frozen', 'frozen')


@admin_bp.route('/users/<int:user_id>/disable', methods=['POST'])
@admin_required
def disable_user(user_id):
    return _set_status(user_id, 'disabled', 'disabled')


@admin_bp.route('/users/<int:user_id>/reactivate', methods=['POST'])
@admin_required
def reactivate_user(user_id):
    return _set_status(user_id, 'active', 'active')


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = _generate_password()
    user.set_password(new_password)
    db.session.commit()
    return redirect(url_for('admin.users', issued=new_password, username=user.username))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user account (admin cannot delete themselves)."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own admin account.', 'danger')
        return redirect(url_for('admin.users'))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" has been deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/scraper-status')
@login_required
@admin_required
def scraper_status():
    """Admin dashboard showing scraper status and logs"""

    # Expire cached objects so we see writes from the scraper subprocess
    db.session.expire_all()

    # Get latest scraper runs (last 20)
    recent_runs = ScraperRun.query.order_by(ScraperRun.started_at.desc()).limit(20).all()

    # Get the most recent run
    latest_run = recent_runs[0] if recent_runs else None

    # Get next scheduled run time (Sunday at 2 AM)
    now = datetime.utcnow()
    next_run = None
    # Calculate next Sunday at 2 AM
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 2:
        days_until_sunday = 7
    next_run = (now + timedelta(days=days_until_sunday)).replace(hour=2, minute=0, second=0, microsecond=0)

    # Get overall statistics
    total_jobs = Job.query.count()
    jobs_last_7_days = Job.query.filter(
        Job.first_seen >= datetime.utcnow() - timedelta(days=7)
    ).count()

    # Get per-company statistics
    stats = JobService.get_statistics()

    # Read recent error logs from file
    log_file = 'data/logs/scraper.log'
    recent_logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Get last 100 lines, reversed to show newest first
                recent_logs = list(reversed(lines[-100:])) if lines else []
        except Exception as e:
            recent_logs = [f"Error reading log file: {str(e)}"]

    return render_template(
        'admin/scraper_status.html',
        recent_runs=recent_runs,
        latest_run=latest_run,
        next_run=next_run,
        total_jobs=total_jobs,
        jobs_last_7_days=jobs_last_7_days,
        stats=stats,
        recent_logs=recent_logs
    )


@admin_bp.route('/scraper-run/<int:run_id>')
@login_required
@admin_required
def scraper_run_detail(run_id):
    """View details of a specific scraper run"""
    run = ScraperRun.query.get_or_404(run_id)
    return render_template('admin/scraper_run_detail.html', run=run)


@admin_bp.route('/run-scraper', methods=['POST'])
@login_required
@admin_required
def run_scraper():
    """Manually trigger scraper run in background"""
    from flask import request
    try:
        # Check if a scraper is genuinely running (started within last 4 hours)
        cutoff = datetime.utcnow() - timedelta(hours=4)
        running = ScraperRun.query.filter(
            ScraperRun.status == 'running',
            ScraperRun.started_at > cutoff
        ).first()
        if running:
            flash('Scraper is already running! Please wait for it to complete.', 'warning')
            return redirect(url_for('admin.scraper_status'))

        # Build command arguments
        cmd = [sys.executable, 'scraper_runner.py', 'manual']

        # Check for skip_scraped option (skip companies already scraped today)
        if request.form.get('skip_scraped') == '1':
            cmd.append('--skip-scraped-today')

        # Run scraper in background. The scraper process already writes to
        # data/logs/scraper.log via FileHandler, so suppress stdout/stderr here
        # to avoid duplicate log lines.
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
            close_fds=True
        )

        flash('Scraper started successfully! Check the dashboard for progress.', 'success')
    except Exception as e:
        flash(f'Error starting scraper: {str(e)}', 'danger')

    return redirect(url_for('admin.scraper_status'))


@admin_bp.route('/force-stop-scraper', methods=['POST'])
@login_required
@admin_required
def force_stop_scraper():
    """Force-stop a stuck scraper run by marking it as failed"""
    stuck_runs = ScraperRun.query.filter(ScraperRun.status == 'running').all()
    count = 0
    for run in stuck_runs:
        run.status = 'failed'
        run.completed_at = datetime.utcnow()
        run.current_company = None
        run.error_log = (run.error_log or '') + '\nForce-stopped by admin'
        if run.started_at:
            run.duration_seconds = (datetime.utcnow() - run.started_at).total_seconds()
        count += 1
    db.session.commit()
    if count:
        flash(f'Force-stopped {count} stuck run(s). You can now restart the scraper.', 'warning')
    else:
        flash('No running scrapers found.', 'info')
    return redirect(url_for('admin.scraper_status'))


@admin_bp.route('/api/scraper-status')
@login_required
@admin_required
def api_scraper_status():
    """API endpoint for scraper status (for AJAX updates)"""
    # Expire all cached objects so we read fresh data from DB
    db.session.expire_all()

    latest_run = ScraperRun.query.order_by(ScraperRun.started_at.desc()).first()

    # Auto-detect stuck runs: if running for > 2 hours with no progress, mark as failed
    if latest_run and latest_run.is_running and latest_run.started_at:
        age = (datetime.utcnow() - latest_run.started_at).total_seconds()
        if age > 7200:  # 2 hours
            latest_run.status = 'failed'
            latest_run.completed_at = datetime.utcnow()
            latest_run.current_company = None
            latest_run.duration_seconds = age
            latest_run.error_log = (latest_run.error_log or '') + '\nAuto-stopped: no progress for 2+ hours'
            db.session.commit()

    # Calculate next Sunday at 2 AM
    now = datetime.utcnow()
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 2:
        days_until_sunday = 7
    next_run = (now + timedelta(days=days_until_sunday)).replace(hour=2, minute=0, second=0, microsecond=0)

    # Read total_companies from the run record (fallback to 19 for old runs)
    total_companies = (latest_run.total_companies if latest_run and latest_run.total_companies else 19)

    response = {
        'latest_run': latest_run.to_dict() if latest_run else None,
        'next_run': next_run.isoformat() if next_run else None,
        'is_running': latest_run.is_running if latest_run else False,
        'total_companies': total_companies,
    }

    if latest_run and latest_run.is_running:
        done = (latest_run.companies_scraped or 0) + (latest_run.companies_failed or 0)
        response['progress_pct'] = int((done / total_companies) * 100) if total_companies > 0 else 0
        response['companies_done'] = done
        response['current_company'] = latest_run.current_company

    return jsonify(response)


@admin_bp.route('/users/<int:user_id>/access', methods=['POST'])
@admin_required
def set_access(user_id):
    """Update which apps a user can access (admins bypass and stay full)."""
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Admin accounts always have access to every app.', 'info')
        return redirect(url_for('admin.users'))
    user.set_allowed_apps(request.form.getlist('allowed_apps'))
    db.session.commit()
    flash(f"Access for '{user.username}' updated to: {user.allowed_apps or '(none)'}.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/profile', methods=['POST'])
@admin_required
def update_profile(user_id):
    """Update a user's student-roster fields (college, major, grad year, etc.)."""
    user = User.query.get_or_404(user_id)

    user.college = (request.form.get('college', '') or '').strip() or None
    user.major = (request.form.get('major', '') or '').strip() or None
    user.sessions = (request.form.get('sessions', '') or '').strip() or None
    user.offers = (request.form.get('offers', '') or '').strip() or None
    user.is_done = request.form.get('is_done') == 'on'

    grad_raw = (request.form.get('graduation_year', '') or '').strip()
    if grad_raw:
        try:
            user.graduation_year = int(grad_raw)
        except ValueError:
            flash('Graduation year must be a number.', 'danger')
            return redirect(url_for('admin.users'))
    else:
        user.graduation_year = None

    db.session.commit()
    flash(f"Profile updated for '{user.username}'.", 'success')
    return redirect(url_for('admin.users'))


# ---- Mentor curriculum & rate -------------------------------------------

@admin_bp.route('/users/<int:user_id>/curriculums', methods=['POST'])
@admin_required
def set_curriculums(user_id):
    """Update which curriculums a mentor may view."""
    user = User.query.get_or_404(user_id)
    if not user.is_mentor:
        flash('Curriculum access applies to mentor accounts only.', 'info')
        return redirect(url_for('admin.users'))
    user.set_allowed_curriculums(request.form.getlist('allowed_curriculums'))
    db.session.commit()
    flash(f"Curriculum access for '{user.username}' updated.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/mentors/<int:user_id>/rate', methods=['POST'])
@admin_required
def set_rate(user_id):
    """Set a new effective-dated hourly rate; closes the previous open rate."""
    user = User.query.get_or_404(user_id)
    if not user.is_mentor:
        flash('Hourly rates apply to mentor accounts only.', 'danger')
        return redirect(url_for('admin.users'))
    raw = (request.form.get('hourly_rate', '') or '').strip()
    currency = (request.form.get('currency', '') or user.payout_currency or 'USD').strip().upper()[:3] or 'USD'
    try:
        rate = Decimal(raw)
        if rate < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash('Enter a valid hourly rate.', 'danger')
        return redirect(url_for('admin.users'))
    now = datetime.utcnow()
    has_prior = MentorRate.query.filter_by(mentor_id=user.id).count() > 0
    # The first rate applies retroactively (covers sessions logged before it was
    # set); later changes take effect from now.
    effective_from = now if has_prior else datetime(1970, 1, 1)
    for open_rate in MentorRate.query.filter_by(mentor_id=user.id, effective_to=None).all():
        open_rate.effective_to = now
    db.session.add(MentorRate(
        mentor_id=user.id, hourly_rate=rate, currency=currency, effective_from=effective_from,
    ))
    db.session.commit()
    flash(f"New rate for '{user.username}': {rate} {currency} / hour.", 'success')
    return redirect(url_for('admin.users'))


# ---- Student payments ----------------------------------------------------

@admin_bp.route('/payments')
@admin_required
def payments():
    pays = StudentPayment.query.order_by(StudentPayment.paid_at.desc()).limit(200).all()
    students = sorted(
        User.query.filter_by(is_admin=False, is_mentor=False).all(),
        key=lambda u: (u.full_name or u.username).lower(),
    )
    total_usd = sum((p.amount_usd or 0) for p in pays)
    return render_template('admin/payments.html', payments=pays, students=students, total_usd=total_usd)


@admin_bp.route('/payments/create', methods=['POST'])
@admin_required
def create_payment():
    student = User.query.get(request.form.get('student_id', type=int))
    amount_raw = (request.form.get('amount', '') or '').strip()
    currency = (request.form.get('currency', 'CNY') or 'CNY').strip().upper()[:3] or 'CNY'
    fx_raw = (request.form.get('fx_to_usd', '') or '').strip()
    # Default the USD/CNY rate from the student's account when left blank.
    if not fx_raw and student and student.exchange_rate:
        fx_raw = str(student.exchange_rate)
    paid_raw = (request.form.get('paid_at', '') or '').strip()
    note = (request.form.get('note', '') or '').strip() or None

    errors = []
    if not student or student.is_admin or student.is_mentor:
        errors.append('Pick a valid student.')
    try:
        amount = Decimal(amount_raw)
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append('Enter a valid payment amount.')
        amount = None
    try:
        fx = Decimal(fx_raw) if fx_raw else None
        if fx is None or fx <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append('Enter a valid USD/CNY rate (or set one on the student account).')
        fx = None
    paid_at = datetime.utcnow()
    if paid_raw:
        try:
            paid_at = datetime.strptime(paid_raw, '%Y-%m-%d')
        except ValueError:
            errors.append('Payment date must be YYYY-MM-DD.')

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('admin.payments'))

    payment = StudentPayment(
        student_id=student.id, amount=amount, currency=currency,
        fx_to_usd=fx, paid_at=paid_at, note=note,
    )
    payment.recompute_usd()
    db.session.add(payment)
    db.session.commit()
    flash(f"Recorded {amount} {currency} from {student.full_name or student.username}.", 'success')
    return redirect(url_for('admin.payments'))


# ---- Weekly reconciliation & payroll ------------------------------------

def _week_bounds(anchor: datetime):
    """(Monday 00:00, next Monday 00:00) UTC for the week containing `anchor`."""
    start = (anchor - timedelta(days=anchor.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def _reconcile_week(start: datetime, end: datetime):
    """Compute per-mentor cost and total revenue for the [start, end) week."""
    sessions = SessionRecord.query.filter(
        SessionRecord.status == 'approved',
        SessionRecord.mentor_id.isnot(None),
        SessionRecord.created_at >= start,
        SessionRecord.created_at < end,
    ).all()

    per_mentor = {}
    for s in sessions:
        if s.mentor is None:
            continue  # mentor account was deleted; cannot attribute cost
        rate = MentorRate.effective_at(s.mentor_id, s.created_at)
        hours = Decimal(s.hours or 0)
        line_amt = hours * (rate.hourly_rate if rate else Decimal(0))
        row = per_mentor.setdefault(s.mentor_id, {
            'mentor': s.mentor, 'hours': Decimal(0), 'count': 0,
            'amount': Decimal(0), 'currency': (rate.currency if rate else
                                               (s.mentor.payout_currency if s.mentor else 'USD')),
            'missing_rate': False,
        })
        row['hours'] += hours
        row['count'] += 1
        row['amount'] += line_amt
        if rate is None:
            row['missing_rate'] = True

    # Existing payouts for this week (issued) keyed by mentor.
    issued = {p.mentor_id: p for p in MentorPayout.query.filter_by(week_start=start).all()}
    for mid, row in per_mentor.items():
        payout = issued.get(mid)
        row['issued'] = payout is not None
        row['fx_to_usd'] = payout.fx_to_usd if payout else (Decimal(1) if row['currency'] == 'USD' else None)
        row['amount_usd'] = (payout.amount_usd if payout else
                             (row['amount'] if row['currency'] == 'USD' else None))

    payments = StudentPayment.query.filter(
        StudentPayment.paid_at >= start, StudentPayment.paid_at < end,
    ).all()
    revenue_usd = sum((p.amount_usd or Decimal(0)) for p in payments)
    cost_usd = sum((r['amount_usd'] or Decimal(0)) for r in per_mentor.values())
    # Cost is understated if any un-issued mentor's USD amount is unknown
    # (a non-USD mentor with no FX yet); surface that rather than hide it.
    cost_incomplete = any(r['amount_usd'] is None for r in per_mentor.values())
    return {
        'rows': sorted(per_mentor.values(),
                       key=lambda r: (r['mentor'].full_name or r['mentor'].username).lower()),
        'payments': payments,
        'revenue_usd': revenue_usd,
        'cost_usd': cost_usd,
        'margin_usd': revenue_usd - cost_usd,
        'cost_incomplete': cost_incomplete,
    }


@admin_bp.route('/reconciliation')
@admin_required
def reconciliation():
    week_param = (request.args.get('week', '') or '').strip()
    anchor = datetime.utcnow()
    if week_param:
        try:
            anchor = datetime.strptime(week_param, '%Y-%m-%d')
        except ValueError:
            flash('Week must be a YYYY-MM-DD date.', 'warning')
    start, end = _week_bounds(anchor)
    report = _reconcile_week(start, end)
    return render_template(
        'admin/reconciliation.html',
        report=report,
        week_start=start,
        week_end=end,
        prev_week=(start - timedelta(days=7)).strftime('%Y-%m-%d'),
        next_week=(start + timedelta(days=7)).strftime('%Y-%m-%d'),
    )


@admin_bp.route('/reconciliation/issue', methods=['POST'])
@admin_required
def issue_payroll():
    """Snapshot each mentor's weekly total into MentorPayout (idempotent)."""
    try:
        start = datetime.strptime(request.form.get('week_start', ''), '%Y-%m-%d')
    except ValueError:
        flash('Missing or invalid week.', 'danger')
        return redirect(url_for('admin.reconciliation'))
    start, end = _week_bounds(start)
    report = _reconcile_week(start, end)
    now = datetime.utcnow()
    issued_count = 0
    skipped = []
    for row in report['rows']:
        mentor = row['mentor']
        if mentor is None or row['issued']:
            continue  # already paid for this week (idempotent)
        fx_raw = (request.form.get(f'fx_{mentor.id}', '') or '').strip()
        if fx_raw:
            try:
                fx = Decimal(fx_raw)
            except InvalidOperation:
                fx = None
        else:
            # Decimal(1) for USD mentors; None for non-USD (must be supplied).
            fx = row['fx_to_usd']
        if fx is None or fx <= 0:
            skipped.append(mentor.full_name or mentor.username)
            continue  # never lock in a wrong USD figure for a foreign currency
        # USD = amount / (USD/CNY rate); USD-currency mentors use rate 1.
        amount_usd = (Decimal(row['amount']) / fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        db.session.add(MentorPayout(
            mentor_id=mentor.id, week_start=start, week_end=end,
            total_hours=row['hours'], session_count=row['count'],
            amount=row['amount'], currency=row['currency'],
            fx_to_usd=fx, amount_usd=amount_usd,
            status='issued', issued_at=now,
        ))
        issued_count += 1
    db.session.commit()
    flash(f"Issued salary for {issued_count} mentor(s) for week of {start:%Y-%m-%d}.", 'success')
    if skipped:
        flash("Skipped (enter a USD/CNY rate first): " + ", ".join(skipped), 'warning')
    return redirect(url_for('admin.reconciliation', week=start.strftime('%Y-%m-%d')))

