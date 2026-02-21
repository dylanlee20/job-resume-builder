"""API routes for job data"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.database import db
from models.job import Job

api_bp = Blueprint('api', __name__, url_prefix='/api')


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
    
    notes = request.json.get('notes', '')
    job.user_notes = notes
    db.session.commit()
    
    return jsonify({
        'success': True,
        'notes': job.user_notes
    })
