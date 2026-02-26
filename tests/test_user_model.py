"""Tests for the User model: password, email verification, tier, serialization."""
from datetime import datetime

import pytest

from models.database import db
from models.user import User, create_admin_user


# =========================================================================
# Password hashing
# =========================================================================

class TestPassword:
    """User.set_password / check_password"""

    def test_set_password_hashes_value(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.password_hash is not None
            assert user.password_hash != 'password123'

    def test_check_password_correct(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.check_password('password123') is True

    def test_check_password_wrong(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.check_password('wrongpassword') is False

    def test_check_password_empty(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.check_password('') is False

    def test_set_password_changes_hash(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            old_hash = user.password_hash
            user.set_password('newpassword456')
            assert user.password_hash != old_hash
            assert user.check_password('newpassword456') is True
            assert user.check_password('password123') is False


# =========================================================================
# Email verification
# =========================================================================

class TestEmailVerification:
    """User.mark_email_verified / needs_email_verification"""

    def test_mark_email_verified(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.email_verified is False
            assert user.email_verified_at is None
            user.mark_email_verified()
            assert user.email_verified is True
            assert user.email_verified_at is not None
            assert isinstance(user.email_verified_at, datetime)

    def test_needs_verification_unverified(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.needs_email_verification() is True

    def test_needs_verification_verified(self, app, verified_user):
        with app.app_context():
            user = User.query.get(verified_user.id)
            assert user.needs_email_verification() is False

    def test_admin_never_needs_verification(self, app, admin_user):
        with app.app_context():
            user = User.query.get(admin_user.id)
            user.email_verified = False
            assert user.needs_email_verification() is False


# =========================================================================
# Tier helpers
# =========================================================================

class TestTierHelpers:

    def test_free_user_is_free(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.is_free is True
            assert user.is_premium is False

    def test_premium_user_is_premium(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            user.tier = 'premium'
            assert user.is_premium is True
            assert user.is_free is False


# =========================================================================
# record_login
# =========================================================================

class TestRecordLogin:

    def test_record_login_sets_timestamp(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            assert user.last_login is None
            user.record_login()
            assert user.last_login is not None
            assert isinstance(user.last_login, datetime)


# =========================================================================
# to_dict serialization
# =========================================================================

class TestToDict:

    def test_to_dict_contains_expected_keys(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            d = user.to_dict()
            expected_keys = {'id', 'username', 'email', 'tier', 'is_admin',
                             'email_verified', 'created_at', 'last_login'}
            assert set(d.keys()) == expected_keys

    def test_to_dict_no_sensitive_fields(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            d = user.to_dict()
            assert 'password_hash' not in d

    def test_to_dict_values(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            d = user.to_dict()
            assert d['username'] == 'testuser'
            assert d['email'] == 'test@example.com'
            assert d['tier'] == 'free'
            assert d['is_admin'] is False
            assert d['email_verified'] is False


# =========================================================================
# __repr__
# =========================================================================

class TestRepr:

    def test_repr_format(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user.id)
            r = repr(user)
            assert 'testuser' in r
            assert 'free' in r
            assert 'verified=False' in r


# =========================================================================
# create_admin_user helper
# =========================================================================

class TestCreateAdminUser:

    def test_creates_new_admin(self, app, db):
        with app.app_context():
            admin = create_admin_user('newadmin', 'securepass', 'newadmin@test.com')
            assert admin.username == 'newadmin'
            assert admin.is_admin is True
            assert admin.email_verified is True
            assert admin.email_verified_at is not None
            assert admin.tier == 'premium'
            assert admin.check_password('securepass') is True

    def test_idempotent_returns_existing(self, app, db):
        with app.app_context():
            admin1 = create_admin_user('sameadmin', 'pass1', 'same@test.com')
            admin2 = create_admin_user('sameadmin', 'pass2', 'different@test.com')
            assert admin1.id == admin2.id

    def test_ensures_existing_admin_is_verified(self, app, db):
        with app.app_context():
            admin = create_admin_user('fixadmin', 'pass', 'fix@test.com')
            admin.email_verified = False
            db.session.commit()
            admin2 = create_admin_user('fixadmin', 'pass', 'fix@test.com')
            assert admin2.email_verified is True
            assert admin2.email_verified_at is not None
