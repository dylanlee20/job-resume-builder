"""Admin routes for scraper monitoring and user management"""
from flask import Blueprint, render_template, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from functools import wraps
from models.database import db
from models.scraper_run import ScraperRun
from models.job import Job
from services.job_service import JobService
from datetime import datetime, timedelta
import os
import sys
import subprocess

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('web.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/users')
@admin_required
def users():
    """Admin user management (placeholder)"""
    return render_template('admin/users.html')


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
    ai_proof_jobs = Job.query.filter_by(is_ai_proof=True).count()
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
        ai_proof_jobs=ai_proof_jobs,
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

        # Run scraper in background using subprocess
        # This prevents the HTTP request from timing out
        # Pass 'manual' as the trigger argument
        subprocess.Popen(
            [sys.executable, 'scraper_runner.py', 'manual'],
            stdout=open('data/logs/scraper.log', 'a'),
            stderr=subprocess.STDOUT,
            cwd=os.getcwd()
        )

        flash('✓ Scraper started successfully! Check the dashboard for progress.', 'success')
    except Exception as e:
        flash(f'Error starting scraper: {str(e)}', 'danger')

    return redirect(url_for('admin.scraper_status'))


@admin_bp.route('/api/scraper-status')
@login_required
@admin_required
def api_scraper_status():
    """API endpoint for scraper status (for AJAX updates)"""
    # Expire all cached objects so we read fresh data from DB
    # (the scraper subprocess writes to the same DB from a separate process)
    db.session.expire_all()

    latest_run = ScraperRun.query.order_by(ScraperRun.started_at.desc()).first()

    # Calculate next Sunday at 2 AM
    now = datetime.utcnow()
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 2:
        days_until_sunday = 7
    next_run = (now + timedelta(days=days_until_sunday)).replace(hour=2, minute=0, second=0, microsecond=0)

    # Total companies for progress calculation
    total_companies = 19

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

    return jsonify(response)
