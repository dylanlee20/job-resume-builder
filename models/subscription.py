"""Subscription model for Stripe integration"""
from datetime import datetime
from models.database import db


class Subscription(db.Model):
    """User subscription tracking"""
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Stripe identifiers
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    stripe_customer_id = db.Column(db.String(255), nullable=True, index=True)
    
    # Subscription details
    plan = db.Column(db.String(50), nullable=False)  # 'monthly', 'yearly', 'one_time'
    status = db.Column(db.String(20), nullable=False, index=True)
    # Status values: 'active', 'cancelled', 'past_due', 'expired'
    
    # Billing period
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', back_populates='subscriptions')
    payments = db.relationship('Payment', back_populates='subscription', lazy='dynamic', cascade='all, delete-orphan')

    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active'
    
    def is_valid(self):
        """Check if subscription is valid (active and not expired)"""
        if not self.is_active():
            return False
        if self.current_period_end and datetime.utcnow() > self.current_period_end:
            return False
        return True

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'stripe_subscription_id': self.stripe_subscription_id,
            'stripe_customer_id': self.stripe_customer_id,
            'plan': self.plan,
            'status': self.status,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active(),
            'is_valid': self.is_valid(),
        }

    def __repr__(self):
        return f'<Subscription {self.id} - User {self.user_id} [{self.status}]>'


class Payment(db.Model):
    """Payment transaction audit trail"""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True, index=True)
    
    # Stripe identifiers
    stripe_payment_intent_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    
    # Payment details
    amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    currency = db.Column(db.String(3), default='usd', nullable=False)
    status = db.Column(db.String(20), nullable=False, index=True)
    # Status values: 'succeeded', 'failed', 'pending', 'refunded'
    
    description = db.Column(db.String(255), nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    subscription = db.relationship('Subscription', back_populates='payments')

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'subscription_id': self.subscription_id,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        amount_str = f"${self.amount/100:.2f}" if self.currency == 'usd' else f"{self.amount} {self.currency}"
        return f'<Payment {self.id} - {amount_str} [{self.status}]>'
