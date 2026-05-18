"""Web routes for main pages"""
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from services.job_service import JobService

web_bp = Blueprint('web', __name__)


@web_bp.before_request
def gate_main_app():
    """Block students without 'main' access from any page served by web_bp.

    Anonymous users pass through (per-route @login_required handles login).
    Admins always pass. Active students without 'main' get the no-access page.
    """
    if not current_user.is_authenticated:
        return None
    if current_user.is_admin or current_user.has_app('main'):
        return None
    return redirect(url_for('auth.no_access'))


@web_bp.route('/')
def index():
    """Auth users go to dashboard, everyone else sees the login page."""
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))
    return redirect(url_for('auth.login'))


@web_bp.route('/dashboard')
@login_required
def dashboard():
    """Main job listings page (logged-in users)."""
    country = request.args.get('country', '').strip()
    location = request.args.get('location', '').strip()
    filters = {
        'q': request.args.get('q', '').strip(),
        'company': request.args.get('company', ''),
        'country': country,
        'city': request.args.get('city', '').strip(),
        'location': location,
        'job_type': request.args.get('job_type', '').strip(),
        'sort_by': request.args.get('sort_by', 'newest'),
        'is_important': request.args.get('starred') == '1',
    }

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    result = JobService.get_jobs(filters=filters, page=page, per_page=per_page)

    companies = JobService.get_all_companies()
    countries = JobService.get_all_countries()
    cities = JobService.get_all_cities(country=country or None)
    job_types = JobService.get_all_job_types()
    stats = JobService.get_statistics()

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
        stats=stats,
        filters=filters,
        prev_url=prev_url,
        next_url=next_url,
    )
