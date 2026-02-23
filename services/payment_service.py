"""Payment service for Stripe integration"""
import stripe
import logging
from datetime import datetime
from config import Config
from models.database import db
from models.user import User
from models.subscription import Subscription, Payment

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = Config.STRIPE_SECRET_KEY


class PaymentService:
    """Service for handling Stripe payments and subscriptions"""

    @staticmethod
    def get_or_create_stripe_customer(user):
        """Get existing or create new Stripe customer for user"""
        if user.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(user.stripe_customer_id)
                if not customer.get('deleted'):
                    return customer
            except stripe.error.InvalidRequestError:
                logger.warning(f"Stripe customer {user.stripe_customer_id} not found, creating new")

        customer = stripe.Customer.create(
            email=user.email,
            metadata={
                'user_id': str(user.id),
                'username': user.username
            }
        )

        user.stripe_customer_id = customer.id
        db.session.commit()
        logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
        return customer

    @staticmethod
    def create_checkout_session(user, plan, success_url, cancel_url):
        """Create Stripe Checkout session for subscription"""
        customer = PaymentService.get_or_create_stripe_customer(user)

        if plan == 'monthly':
            price_id = Config.STRIPE_PRICE_ID_MONTHLY
        elif plan == 'annual':
            price_id = Config.STRIPE_PRICE_ID_ANNUAL
        else:
            raise ValueError(f"Invalid plan: {plan}")

        if not price_id or price_id == 'price_placeholder':
            raise ValueError("Stripe price ID not configured")

        session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': str(user.id),
                'plan': plan
            },
            subscription_data={
                'metadata': {
                    'user_id': str(user.id),
                    'plan': plan
                }
            },
            allow_promotion_codes=True,
        )

        logger.info(f"Created checkout session {session.id} for user {user.id} ({plan})")
        return session

    @staticmethod
    def handle_checkout_completed(session):
        """Handle checkout.session.completed webhook event"""
        user_id = session.get('metadata', {}).get('user_id')
        plan = session.get('metadata', {}).get('plan', 'monthly')
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        if not user_id:
            logger.error("Checkout session missing user_id in metadata")
            return

        user = User.query.get(int(user_id))
        if not user:
            logger.error(f"User {user_id} not found for checkout session")
            return

        if customer_id and not user.stripe_customer_id:
            user.stripe_customer_id = customer_id

        # Create or update subscription record
        sub = Subscription.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not sub:
            sub = Subscription(
                user_id=user.id,
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                plan=plan,
                status='active',
                current_period_start=datetime.utcnow(),
            )
            db.session.add(sub)
        else:
            sub.status = 'active'
            sub.plan = plan

        user.upgrade_to_premium()
        db.session.commit()
        logger.info(f"User {user.id} upgraded to premium ({plan}) via checkout")

    @staticmethod
    def handle_subscription_updated(stripe_subscription):
        """Handle customer.subscription.updated webhook event"""
        subscription_id = stripe_subscription.get('id')
        status = stripe_subscription.get('status')

        sub = Subscription.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not sub:
            logger.warning(f"Subscription {subscription_id} not found in database")
            return

        status_map = {
            'active': 'active',
            'past_due': 'past_due',
            'canceled': 'cancelled',
            'unpaid': 'past_due',
            'incomplete': 'past_due',
            'incomplete_expired': 'expired',
            'trialing': 'active',
        }

        sub.status = status_map.get(status, status)

        current_period = stripe_subscription.get('current_period_start')
        if current_period:
            sub.current_period_start = datetime.fromtimestamp(current_period)
        current_period_end = stripe_subscription.get('current_period_end')
        if current_period_end:
            sub.current_period_end = datetime.fromtimestamp(current_period_end)

        user = User.query.get(sub.user_id)
        if user:
            if sub.status == 'active':
                user.upgrade_to_premium()
            elif sub.status in ('cancelled', 'expired'):
                other_active = Subscription.query.filter(
                    Subscription.user_id == user.id,
                    Subscription.id != sub.id,
                    Subscription.status == 'active'
                ).first()
                if not other_active:
                    user.downgrade_to_free()

        db.session.commit()
        logger.info(f"Subscription {subscription_id} updated to {sub.status}")

    @staticmethod
    def handle_subscription_deleted(stripe_subscription):
        """Handle customer.subscription.deleted webhook event"""
        subscription_id = stripe_subscription.get('id')

        sub = Subscription.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not sub:
            logger.warning(f"Subscription {subscription_id} not found for deletion")
            return

        sub.status = 'cancelled'

        user = User.query.get(sub.user_id)
        if user:
            other_active = Subscription.query.filter(
                Subscription.user_id == user.id,
                Subscription.id != sub.id,
                Subscription.status == 'active'
            ).first()
            if not other_active:
                user.downgrade_to_free()

        db.session.commit()
        logger.info(f"Subscription {subscription_id} cancelled, user {sub.user_id} downgraded")

    @staticmethod
    def handle_invoice_payment_succeeded(invoice):
        """Handle invoice.payment_succeeded webhook event"""
        customer_id = invoice.get('customer')
        subscription_id = invoice.get('subscription')
        amount = invoice.get('amount_paid', 0)
        payment_intent_id = invoice.get('payment_intent')

        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if not user:
            logger.warning(f"User not found for customer {customer_id}")
            return

        sub = Subscription.query.filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        # Idempotency check
        if payment_intent_id:
            existing = Payment.query.filter_by(
                stripe_payment_intent_id=payment_intent_id
            ).first()
            if existing:
                logger.info(f"Payment {payment_intent_id} already recorded, skipping")
                return

        payment = Payment(
            user_id=user.id,
            subscription_id=sub.id if sub else None,
            stripe_payment_intent_id=payment_intent_id,
            amount=amount,
            currency=invoice.get('currency', 'usd'),
            status='succeeded',
            description=f"Subscription payment - {sub.plan if sub else 'unknown'}"
        )
        db.session.add(payment)
        db.session.commit()
        logger.info(f"Payment recorded: ${amount / 100:.2f} from user {user.id}")

    @staticmethod
    def handle_invoice_payment_failed(invoice):
        """Handle invoice.payment_failed webhook event"""
        customer_id = invoice.get('customer')
        payment_intent_id = invoice.get('payment_intent')

        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if not user:
            return

        payment = Payment(
            user_id=user.id,
            stripe_payment_intent_id=payment_intent_id,
            amount=invoice.get('amount_due', 0),
            currency=invoice.get('currency', 'usd'),
            status='failed',
            description='Subscription payment failed'
        )
        db.session.add(payment)
        db.session.commit()
        logger.warning(f"Payment failed for user {user.id}")

    @staticmethod
    def cancel_subscription(user):
        """Cancel user's active subscription at period end"""
        sub = Subscription.query.filter_by(
            user_id=user.id,
            status='active'
        ).order_by(Subscription.created_at.desc()).first()

        if not sub or not sub.stripe_subscription_id:
            return None, "No active subscription found"

        try:
            stripe_sub = stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True
            )

            sub.current_period_end = datetime.fromtimestamp(
                stripe_sub.current_period_end
            )
            db.session.commit()

            logger.info(f"Subscription {sub.id} set to cancel at period end for user {user.id}")
            return sub, None

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {e}")
            return None, str(e)

    @staticmethod
    def get_active_subscription(user):
        """Get user's current active subscription"""
        return Subscription.query.filter_by(
            user_id=user.id,
            status='active'
        ).order_by(Subscription.created_at.desc()).first()

    @staticmethod
    def get_payment_history(user, limit=10):
        """Get user's recent payment history"""
        return Payment.query.filter_by(
            user_id=user.id
        ).order_by(Payment.created_at.desc()).limit(limit).all()
