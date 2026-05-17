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

    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # 'active' (login OK), 'frozen' (temporarily blocked), 'disabled' (revoked).
    status = db.Column(db.String(20), default='active', nullable=False, index=True)

    # Kept on the model for legacy DB schemas, but never enforced anymore —
    # email verification was disabled when the app moved to admin-issued accounts.
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    # Legacy columns kept NOT NULL in the SQLite schema from an earlier
    # premium-tier / per-user SMTP era. The features are retired but the
    # constraints remain, so the model must supply defaults on INSERT.
    tier = db.Column(db.String(20), default='free', nullable=False)
    smtp_use_tls = db.Column(db.Boolean, default=True, nullable=False)

    # Comma-separated list of app codes the user can reach. Empty = no
    # access to any gated app. Admins bypass this check entirely. See
    # nginx auth_request flow for how this is enforced on /macro and
    # /competitions; the main Flask app gates itself via before_request.
    allowed_apps = db.Column(db.String(100), default='', nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.username} status={self.status}>'

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def mark_email_verified(self) -> None:
        self.email_verified = True
        self.email_verified_at = datetime.utcnow()

    def needs_email_verification(self) -> bool:
        # Email verification was retired in favor of admin-issued accounts.
        return False

    @property
    def is_active_account(self) -> bool:
        return (self.status or 'active') == 'active'

    @property
    def is_frozen(self) -> bool:
        return self.status == 'frozen'

    @property
    def is_disabled(self) -> bool:
        return self.status == 'disabled'

    APP_CODES = ('main', 'macro', 'competitions')

    @property
    def app_set(self) -> set:
        return {a.strip() for a in (self.allowed_apps or '').split(',') if a.strip()}

    def has_app(self, code: str) -> bool:
        if self.is_admin:
            return True
        if not self.is_active_account:
            return False
        return code in self.app_set

    def set_allowed_apps(self, codes) -> None:
        clean = sorted({c for c in codes if c in self.APP_CODES})
        self.allowed_apps = ','.join(clean)

    def record_login(self) -> None:
        self.last_login = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'allowed_apps': sorted(self.app_set),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


def create_admin_user(username: str, password: str, email: str) -> User:
    """Idempotently create the default admin user."""
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
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin
