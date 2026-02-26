"""Tests for EmailVerificationToken model: creation, hashing, verification, expiry."""
from datetime import datetime, timedelta

import pytest

from models.database import db
from models.user import User
from models.email_verification_token import EmailVerificationToken


class TestTokenCreation:

    def test_create_returns_raw_token(self, app, sample_user):
        with app.app_context():
            raw = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            assert isinstance(raw, str)
            assert len(raw) >= 32  # URL-safe base64 of 32 bytes

    def test_raw_token_not_stored_in_db(self, app, sample_user):
        with app.app_context():
            raw = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            record = EmailVerificationToken.query.filter_by(user_id=sample_user.id).first()
            assert record.token_hash != raw

    def test_stored_hash_is_sha256(self, app, sample_user):
        with app.app_context():
            raw = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            record = EmailVerificationToken.query.filter_by(user_id=sample_user.id).first()
            assert len(record.token_hash) == 64  # SHA-256 hex length
            assert record.token_hash == EmailVerificationToken.hash_token(raw)

    def test_expires_at_is_set(self, app, sample_user):
        with app.app_context():
            EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            record = EmailVerificationToken.query.filter_by(user_id=sample_user.id).first()
            assert record.expires_at is not None
            assert record.expires_at > datetime.utcnow()

    def test_used_at_initially_none(self, app, sample_user):
        with app.app_context():
            EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            record = EmailVerificationToken.query.filter_by(user_id=sample_user.id).first()
            assert record.used_at is None

    def test_unique_tokens_each_call(self, app, sample_user):
        with app.app_context():
            raw1 = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            raw2 = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            assert raw1 != raw2

    def test_create_invalidates_old_unused_tokens(self, app, sample_user):
        with app.app_context():
            raw1 = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            hash1 = EmailVerificationToken.hash_token(raw1)

            raw2 = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            # Old token should be deleted
            old = EmailVerificationToken.query.filter_by(token_hash=hash1).first()
            assert old is None

            # New token should exist
            tokens = EmailVerificationToken.query.filter_by(user_id=sample_user.id).all()
            assert len(tokens) == 1


class TestTokenVerification:

    def test_verify_valid_token(self, app, sample_user):
        with app.app_context():
            raw = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            record = EmailVerificationToken.verify(raw)
            assert record is not None
            assert record.user_id == sample_user.id

    def test_verify_wrong_token_returns_none(self, app, sample_user):
        with app.app_context():
            EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()
            record = EmailVerificationToken.verify('completely-wrong-token')
            assert record is None

    def test_verify_expired_token_returns_none(self, app, sample_user):
        with app.app_context():
            raw = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            # Manually expire
            hashed = EmailVerificationToken.hash_token(raw)
            record = EmailVerificationToken.query.filter_by(token_hash=hashed).first()
            record.expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()

            result = EmailVerificationToken.verify(raw)
            assert result is None

    def test_verify_used_token_returns_none(self, app, sample_user):
        with app.app_context():
            raw = EmailVerificationToken.create_for_user(sample_user.id)
            db.session.commit()

            # Mark as used
            hashed = EmailVerificationToken.hash_token(raw)
            record = EmailVerificationToken.query.filter_by(token_hash=hashed).first()
            record.used_at = datetime.utcnow()
            db.session.commit()

            result = EmailVerificationToken.verify(raw)
            assert result is None

    def test_verify_nonexistent_token(self, app):
        with app.app_context():
            result = EmailVerificationToken.verify('nonexistent-token-abc')
            assert result is None


class TestHashToken:

    def test_deterministic(self):
        h1 = EmailVerificationToken.hash_token('test-token')
        h2 = EmailVerificationToken.hash_token('test-token')
        assert h1 == h2

    def test_different_inputs_different_hashes(self):
        h1 = EmailVerificationToken.hash_token('token-a')
        h2 = EmailVerificationToken.hash_token('token-b')
        assert h1 != h2


class TestModelRegistration:
    """Verify EmailVerificationToken is registered with SQLAlchemy metadata
    so that db.create_all() creates its table during app startup."""

    def test_model_in_models_package(self):
        """EmailVerificationToken must be importable from the models package."""
        import models
        assert hasattr(models, 'EmailVerificationToken')

    def test_table_in_metadata(self, app):
        """The email_verification_tokens table must be in SQLAlchemy metadata."""
        with app.app_context():
            table_names = db.metadata.tables.keys()
            assert 'email_verification_tokens' in table_names
