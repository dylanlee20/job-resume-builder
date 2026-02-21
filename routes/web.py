"""Web routes for main pages"""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from services.job_service import JobService

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
@login_required
def index():
    """Main job listings page with compact table view"""
    # Get filter parameters
    filters = {
        'company': request.args.get('company', ''),
        'location': request.args.get('location', ''),
        'ai_proof_category': request.args.get('category', ''),
        'is_important': request.args.get('starred') == '1',
    }
    
    # Get pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)  # More items for compact view
    
    # Get jobs
    result = JobService.get_jobs(filters=filters, page=page, per_page=per_page)
    
    # Get filter options
    companies = JobService.get_all_companies()
    locations = JobService.get_all_locations()
    categories = JobService.get_all_categories()
    stats = JobService.get_statistics()

    return render_template(
        'index.html',
        jobs=result['jobs'],
        total=result['total'],
        page=page,
        pages=result['pages'],
        per_page=per_page,
        has_next=result['has_next'],
        has_prev=result['has_prev'],
        companies=companies,
        locations=locations,
        categories=categories,
        stats=stats,
        filters=filters
    )


@web_bp.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template('pricing.html')
