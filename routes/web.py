"""Web routes for main pages"""
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from services.job_service import JobService

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Landing page for guests, redirect to dashboard for logged-in users"""
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))

    # Public landing page - show stats
    try:
        stats = JobService.get_statistics()
    except Exception:
        stats = {'total_ai_proof_jobs': '500+', 'ai_proof_percentage': 0}

    return render_template('landing.html', stats=stats)


@web_bp.route('/dashboard')
@login_required
def dashboard():
    """Main job listings page with compact table view (logged-in users)"""
    # Get filter parameters
    ai_proof_only = request.args.get('ai_proof') == '1'
    filters = {
        'company': request.args.get('company', ''),
        'location': request.args.get('location', ''),
        'ai_proof_category': request.args.get('category', ''),
        'is_important': request.args.get('starred') == '1',
        'ai_proof_only': ai_proof_only,
    }

    # Get pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    # Get jobs
    result = JobService.get_jobs(filters=filters, page=page, per_page=per_page)

    # Get filter options
    companies = JobService.get_all_companies(include_excluded=True)
    locations = JobService.get_all_locations(include_excluded=True)
    categories = JobService.get_all_categories(include_excluded=True)
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
    """Pricing page - public"""
    return render_template('pricing.html')
