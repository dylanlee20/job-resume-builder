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

    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.username} verified={self.email_verified}>'

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def mark_email_verified(self) -> None:
        self.email_verified = True
        self.email_verified_at = datetime.utcnow()

    def needs_email_verification(self) -> bool:
        return not self.email_verified and not self.is_admin

    def record_login(self) -> None:
        self.last_login = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
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
