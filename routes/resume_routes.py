"""Resume upload and assessment routes"""
from flask import Blueprint, render_template
from flask_login import login_required

resume_bp = Blueprint('resume', __name__, url_prefix='/resume')


@resume_bp.route('/upload')
@login_required
def upload():
    """Resume upload page (placeholder)"""
    return render_template('resume/upload.html')
