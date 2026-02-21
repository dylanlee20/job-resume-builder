"""API routes for job data"""
from flask import Blueprint, jsonify
from flask_login import login_required

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/jobs', methods=['GET'])
@login_required
def get_jobs():
    """Get jobs list (placeholder)"""
    return jsonify({'success': True, 'data': []})
