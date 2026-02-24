"""User model with authentication and email verification support"""
import secrets
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import db
from config import Config


class User(UserMixin, db.Model):
    """User account model"""
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
    email_verification_token = db.Column(db.String(128), nullable=True, index=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)

    # Stripe
    stripe_customer_id = db.Column(db.String(100), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    resumes = db.relationship('Resume', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username} ({self.tier}) verified={self.email_verified}>'

    # ------------------------------------------------------------------
    # Password
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hash and store password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------

    def generate_verification_token(self) -> str:
        """Generate a secure URL-safe verification token and persist it.

        Returns the raw token (to be embedded in the email link).
        Callers must commit the session after calling this.
        """
        token = secrets.token_urlsafe(48)  # 64-char URL-safe string
        self.email_verification_token = token
        self.email_verification_sent_at = datetime.utcnow()
        return token

    def verify_email_token(self, token: str) -> bool:
        """Validate a verification token.

        Returns True and marks the user as verified if the token matches
        and has not expired.  Returns False otherwise.
        """
        if not self.email_verification_token:
            return False
        if self.email_verification_token != token:
            return False

        # Check expiry
        expiry_hours = getattr(Config, 'EMAIL_VERIFICATION_EXPIRY_HOURS', 24)
        if self.email_verification_sent_at:
            age = datetime.utcnow() - self.email_verification_sent_at
            if age > timedelta(hours=expiry_hours):
                return False

        # Mark verified and clear the token
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_sent_at = None
        return True

    def is_verification_token_expired(self) -> bool:
        """Check whether the pending verification token is expired."""
        if not self.email_verification_sent_at:
            return True
        expiry_hours = getattr(Config, 'EMAIL_VERIFICATION_EXPIRY_HOURS', 24)
        age = datetime.utcnow() - self.email_verification_sent_at
        return age > timedelta(hours=expiry_hours)

    def needs_email_verification(self) -> bool:
        """Return True if this user still needs to verify their email."""
        return not self.email_verified and not self.is_admin

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------

    @property
    def is_premium(self) -> bool:
        """Check if user has premium tier"""
        return self.tier == 'premium'

    @property
    def is_free(self) -> bool:
        """Check if user has free tier"""
        return self.tier == 'free'

    def get_active_subscription(self):
        """Get the user's current active subscription, if any"""
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
        """Serialize user to dict (no sensitive fields)"""
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
        # Ensure existing admin is always marked verified
        if not existing.email_verified:
            existing.email_verified = True
            db.session.commit()
        return existing

    admin = User(
        username=username,
        email=email,
        is_admin=True,
        email_verified=True,  # Admins are always pre-verified
        tier='premium',
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin
