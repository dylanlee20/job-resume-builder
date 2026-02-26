"""User model with authentication and email verification support."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from models.database import db


class User(UserMixin, db.Model):
    """User account model."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Account status
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    tier = db.Column(db.String(20), default='free', nullable=False)  # 'free' | 'premium'

    # Email verification
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    # Stripe
    stripe_customer_id = db.Column(db.String(100), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    resumes = db.relationship('Resume', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    assessments = db.relationship('ResumeAssessment', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username} ({self.tier}) verified={self.email_verified}>'

    # ------------------------------------------------------------------
    # Password
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------

    def mark_email_verified(self) -> None:
        """Mark this user's email as verified. Caller must commit."""
        self.email_verified = True
        self.email_verified_at = datetime.utcnow()

    def needs_email_verification(self) -> bool:
        """Return True if this user still needs to verify their email."""
        return not self.email_verified and not self.is_admin

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------

    @property
    def is_premium(self) -> bool:
        return self.tier == 'premium'

    @property
    def is_free(self) -> bool:
        return self.tier == 'free'

    def get_active_subscription(self):
        """Get the user's current active subscription, if any."""
        from models.subscription import Subscription
        return (
            Subscription.query
            .filter_by(user_id=self.id, status='active')
            .first()
        )

    def record_login(self) -> None:
        """Update last_login timestamp. Caller must commit."""
        self.last_login = datetime.utcnow()

    def to_dict(self) -> dict:
        """Serialize user to dict (no sensitive fields)."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'tier': self.tier,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


# ---------------------------------------------------------------------------
# Admin helper (called from app factory)
# ---------------------------------------------------------------------------

def create_admin_user(username: str, password: str, email: str) -> User:
    """Idempotently create the default admin user.

    Admin users are always marked as email_verified so they are never
    blocked by the verification gate.
    """
    existing = User.query.filter_by(username=username).first()
    if existing:
        if not existing.email_verified:
            existing.email_verified = True
            existing.email_verified_at = datetime.utcnow()
            db.session.commit()
        return existing

    admin = User(
        username=username,
        email=email,
        is_admin=True,
        email_verified=True,
        email_verified_at=datetime.utcnow(),
        tier='premium',
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin
