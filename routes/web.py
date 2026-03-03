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
    country = request.args.get('country', '').strip()
    location = request.args.get('location', '').strip()
    filters = {
        'q': request.args.get('q', '').strip(),
        'company': request.args.get('company', ''),
        'country': country,
        'city': request.args.get('city', '').strip(),
        # Backward compatibility for old links using exact location filtering.
        'location': location,
        'job_type': request.args.get('job_type', '').strip(),
        'ai_proof_category': request.args.get('category', ''),
        'sort_by': request.args.get('sort_by', 'newest'),
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
    countries = JobService.get_all_countries(include_excluded=True)
    cities = JobService.get_all_cities(country=country or None, include_excluded=True)
    job_types = JobService.get_all_job_types(include_excluded=True)
    categories = JobService.get_all_categories(include_excluded=True)
    stats = JobService.get_statistics()

    # Build pagination URLs preserving non-page query params.
    pagination_params = {
        key: value for key, value in request.args.items()
        if key != 'page' and str(value).strip() != ''
    }
    prev_url = url_for('web.dashboard', page=page - 1, **pagination_params) if result['has_prev'] else None
    next_url = url_for('web.dashboard', page=page + 1, **pagination_params) if result['has_next'] else None

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
        countries=countries,
        cities=cities,
        job_types=job_types,
        categories=categories,
        stats=stats,
        filters=filters,
        prev_url=prev_url,
        next_url=next_url,
    )


@web_bp.route('/pricing')
def pricing():
    """Pricing page - public"""
    return render_template('pricing.html')
