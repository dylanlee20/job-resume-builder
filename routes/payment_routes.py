"""Payment and subscription routes"""
import stripe
import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from config import Config
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)

payment_bp = Blueprint('payment', __name__)


@payment_bp.route('/api/checkout', methods=['POST'])
@login_required
def create_checkout():
    """Create Stripe Checkout session and return redirect URL"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400

    plan = data.get('plan')
    if plan not in ('monthly', 'annual'):
        return jsonify({'success': False, 'message': 'Invalid plan'}), 400

    if current_user.is_premium:
        return jsonify({'success': False, 'message': 'You already have a premium subscription'}), 400

    try:
        success_url = url_for('payment.payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = url_for('payment.payment_cancel', _external=True)

        session = PaymentService.create_checkout_session(
            user=current_user,
            plan=plan,
            success_url=success_url,
            cancel_url=cancel_url
        )

        return jsonify({
            'success': True,
            'checkout_url': session.url
        })

    except ValueError as e:
        logger.error(f"Checkout config error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        return jsonify({'success': False, 'message': 'Payment service error. Please try again.'}), 500


@payment_bp.route('/payment/success')
@login_required
def payment_success():
    """Payment success redirect page"""
    session_id = request.args.get('session_id')
    return render_template('payment_success.html', session_id=session_id)


@payment_bp.route('/payment/cancel')
@login_required
def payment_cancel():
    """Payment cancelled redirect page"""
    return render_template('payment_cancel.html')


@payment_bp.route('/subscription')
@login_required
def subscription():
    """Subscription management page"""
    active_sub = PaymentService.get_active_subscription(current_user)
    payments = PaymentService.get_payment_history(current_user)
    return render_template(
        'subscription.html',
        subscription=active_sub,
        payments=payments
    )


@payment_bp.route('/api/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel user's active subscription"""
    sub, error = PaymentService.cancel_subscription(current_user)

    if error:
        return jsonify({'success': False, 'message': error}), 400

    return jsonify({
        'success': True,
        'message': 'Subscription will be cancelled at the end of your billing period.',
        'period_end': sub.current_period_end.isoformat() if sub.current_period_end else None
    })


@payment_bp.route('/api/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events with signature verification"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    if not sig_header:
        logger.warning("Webhook received without Stripe-Signature header")
        return jsonify({'error': 'Missing signature'}), 400

    webhook_secret = Config.STRIPE_WEBHOOK_SECRET
    if not webhook_secret or webhook_secret == 'whsec_placeholder':
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return jsonify({'error': 'Webhook not configured'}), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return jsonify({'error': 'Invalid signature'}), 401

    logger.info(f"Webhook received: {event['type']}")

    try:
        event_type = event['type']
        event_data = event['data']['object']

        if event_type == 'checkout.session.completed':
            PaymentService.handle_checkout_completed(event_data)

        elif event_type == 'customer.subscription.updated':
            PaymentService.handle_subscription_updated(event_data)

        elif event_type == 'customer.subscription.deleted':
            PaymentService.handle_subscription_deleted(event_data)

        elif event_type == 'invoice.payment_succeeded':
            PaymentService.handle_invoice_payment_succeeded(event_data)

        elif event_type == 'invoice.payment_failed':
            PaymentService.handle_invoice_payment_failed(event_data)

        else:
            logger.info(f"Unhandled webhook event: {event_type}")

    except Exception as e:
        logger.exception(f"Error handling webhook {event['type']}: {e}")

    return jsonify({'success': True}), 200
