"""API routes for job data"""
import hmac
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.database import db
from models.job import Job
from models.scraper_run import ScraperRun
from services.job_service import JobService
from config import Config

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _has_valid_job_export_token():
    configured = (Config.JOB_EXPORT_TOKEN or '').strip()
    if not configured:
        return False

    auth_header = request.headers.get('Authorization', '')
    bearer_prefix = 'Bearer '
    bearer_token = auth_header[len(bearer_prefix):].strip() if auth_header.startswith(bearer_prefix) else ''
    query_token = (request.args.get('token') or '').strip()

    # Constant-time comparison to avoid leaking the token via timing.
    return (
        (bool(bearer_token) and hmac.compare_digest(bearer_token, configured))
        or (bool(query_token) and hmac.compare_digest(query_token, configured))
    )


@api_bp.route('/jobs/<int:job_id>/star', methods=['POST'])
@login_required
def star_job(job_id):
    """Toggle star/important status for a job"""
    job = Job.query.get_or_404(job_id)
    
    # Toggle is_important
    job.is_important = not job.is_important
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_important': job.is_important
    })


@api_bp.route('/jobs/<int:job_id>/notes', methods=['POST'])
@login_required
def update_notes(job_id):
    """Update notes for a job"""
    job = Job.query.get_or_404(job_id)

    # Tolerate a missing/invalid JSON body instead of raising a 500.
    payload = request.get_json(silent=True) or {}
    notes = payload.get('notes', '')
    job.user_notes = notes
    db.session.commit()
    
    return jsonify({
        'success': True,
        'notes': job.user_notes
    })


@api_bp.route('/internal/jobs-export', methods=['GET'])
def internal_jobs_export():
    """Token-protected export of normalized job data for WhaleStreet ingestion."""
    if not (Config.JOB_EXPORT_TOKEN or '').strip():
        return jsonify({
            'error': 'Job export feed is not configured.',
            'code': 'JOB_EXPORT_DISABLED',
        }), 503

    if not _has_valid_job_export_token():
        return jsonify({
            'error': 'Forbidden',
            'code': 'INVALID_JOB_EXPORT_TOKEN',
        }), 403

    status = (request.args.get('status') or 'active').strip()
    limit = min(max(request.args.get('limit', default=500, type=int), 1), 2000)

    # Front-office roles only by default; pass ai_proof_only=0 for the full feed.
    ai_proof_raw = (request.args.get('ai_proof_only') or '1').strip().lower()
    ai_proof_only = ai_proof_raw not in ('0', 'false', 'no', 'off')

    query = Job.query
    if status:
        query = query.filter_by(status=status)
    if ai_proof_only:
        query = query.filter(Job.is_ai_proof.is_(True))

    jobs = query.order_by(Job.last_updated.desc(), Job.first_seen.desc()).limit(limit).all()
    latest_run = ScraperRun.query.order_by(ScraperRun.started_at.desc()).first()
    stats = JobService.get_statistics()

    return jsonify({
        'exported_at': datetime.utcnow().isoformat(),
        'count': len(jobs),
        'status': status,
        'ai_proof_only': ai_proof_only,
        'latest_run': latest_run.to_dict() if latest_run else None,
        'stats': {
            'total_active_jobs': stats.get('total_active_jobs', 0),
        },
        'jobs': [job.to_dict() for job in jobs],
    })
