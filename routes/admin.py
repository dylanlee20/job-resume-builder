"""Admin routes for scraper monitoring and user management"""
from flask import (
    Blueprint, render_template, redirect, url_for, jsonify, flash, request,
    Response, abort,
)
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from models.database import db
from models.user import User
from models.scraper_run import ScraperRun
from models.session_record import SessionRecord, SESSION_TYPES
from models.question_bank import QuestionBankEntry
from models.job import Job
from services.job_service import JobService
from services.slides_service import render_watermarked_png
from datetime import datetime, timedelta
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
    explicit_password = (request.form.get('password', '') or '').strip()

    errors = []
    if len(username) < 3:
        errors.append('Username must be at least 3 characters.')
    if '@' not in email or len(email) < 5:
        errors.append('A valid email is required.')
    if explicit_password and len(explicit_password) < 8:
        errors.append('Custom password must be at least 8 characters.')
    if User.query.filter(db.func.lower(User.username) == username.lower()).first():
        errors.append(f"Username '{username}' is already taken.")
    if User.query.filter(db.func.lower(User.email) == email).first():
        errors.append(f"Email '{email}' is already in use.")

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('admin.users'))

    password = explicit_password or _generate_password()
    user = User(
        username=username,
        email=email,
        is_admin=make_admin,
        status='active',
        email_verified=True,
        email_verified_at=datetime.utcnow(),
    )
    user.set_password(password)
    user.set_allowed_apps(request.form.getlist('allowed_apps'))
    db.session.add(user)
    db.session.commit()

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

