"""Web routes for main pages"""
from flask import Blueprint, render_template
from flask_login import login_required

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
@login_required
def index():
    """Main job listings page"""
    return render_template('index.html')


@web_bp.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template('pricing.html')
