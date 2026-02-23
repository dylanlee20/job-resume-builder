"""Create a test regular user (non-admin)"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models.database import db
from models.user import User


def create_test_user():
    """Create a test user with username 'student' and password 'student123'"""
    app, _ = create_app()

    with app.app_context():
        # Check if user already exists
        existing = User.query.filter_by(username='student').first()
        if existing:
            print("✓ Test user 'student' already exists")
            print(f"  - Username: student")
            print(f"  - Is Admin: {existing.is_admin}")
            print(f"  - Tier: {existing.tier}")
            return existing

        # Create new regular user (pre-verified for test convenience)
        user = User(
            username='student',
            email='student@newwhale.com',
            is_admin=False,  # Regular user, NOT admin
            email_verified=True,
            tier='free'
        )
        user.set_password('student123')

        db.session.add(user)
        db.session.commit()

        print("=" * 60)
        print("✓ Test user created successfully!")
        print("=" * 60)
        print(f"Username: student")
        print(f"Password: student123")
        print(f"Is Admin: {user.is_admin}")
        print(f"Tier: {user.tier}")
        print("=" * 60)
        print("\nYou can now test regular user access by logging in with:")
        print("  Username: student")
        print("  Password: student123")
        print("\nRegular users should NOT see the Admin menu in the navbar.")
        print("=" * 60)

        return user


if __name__ == '__main__':
    create_test_user()
