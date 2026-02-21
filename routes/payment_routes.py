"""Payment and subscription routes"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from flask_wtf.csrf import CSRFProtect

payment_bp = Blueprint('payment', __name__)
csrf = CSRFProtect()


@payment_bp.route('/api/checkout', methods=['POST'])
@login_required
def create_checkout():
    """Create Stripe checkout session (placeholder)"""
    return jsonify({'success': False, 'message': 'Not implemented yet'})


@payment_bp.route('/api/webhooks/stripe', methods=['POST'])
@csrf.exempt  # Stripe webhooks don't include CSRF tokens
def stripe_webhook():
    """Handle Stripe webhooks (placeholder)"""
    return jsonify({'success': True})
