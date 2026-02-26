"""Email verification token model — stores only hashed tokens."""
import hashlib
import secrets
from datetime import datetime, timedelta

from models.database import db
from config import Config


class EmailVerificationToken(db.Model):
    """One-time-use email verification tokens.

    Security: only the SHA-256 hash of the token is stored.
    The raw token is returned once at creation time (for the email link)
    and never persisted.
    """
    __tablename__ = 'email_verification_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('verification_tokens', lazy='dynamic', cascade='all, delete-orphan'))

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Return the SHA-256 hex digest of a raw token."""
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @classmethod
    def create_for_user(cls, user_id: int) -> str:
        """Generate a new verification token for a user.

        Invalidates any existing unused tokens for this user.
        Returns the raw token (caller must send it in the email link).
        Caller must commit the session.
        """
        # Invalidate existing unused tokens for this user
        cls.query.filter_by(user_id=user_id, used_at=None).delete()

        raw_token = secrets.token_urlsafe(32)  # 32 bytes = 43-char URL-safe string
        expiry_minutes = getattr(Config, 'EMAIL_VERIFICATION_EXPIRY_MINUTES', 30)

        token_record = cls(
            user_id=user_id,
            token_hash=cls.hash_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        )
        db.session.add(token_record)
        return raw_token

    @classmethod
    def verify(cls, raw_token: str):
        """Look up and validate a raw token.

        Returns the token record if valid, None otherwise.
        Does NOT mark it as used — caller should set used_at and commit.
        """
        hashed = cls.hash_token(raw_token)
        record = cls.query.filter_by(token_hash=hashed).first()

        if record is None:
            return None
        if record.used_at is not None:
            return None
        if datetime.utcnow() > record.expires_at:
            return None

        return record
