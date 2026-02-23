"""Migration to add email verification columns to users table.

This uses raw sqlite3 to avoid the chicken-and-egg problem where
SQLAlchemy models reference columns that don't exist yet.

Run this on the VPS after pulling:
    cd ~/job-resume-builder
    python3 migrations/add_email_verification.py
"""
import sys
import os
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Determine DB path from config or use default
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'jobs.db')


def get_existing_columns(conn):
    """Get set of existing column names for users table"""
    cursor = conn.execute("PRAGMA table_info(users)")
    return {row[1] for row in cursor.fetchall()}


def migrate():
    """Add email_verified, email_verification_token, and email_verification_sent_at to users"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("If your DB is elsewhere, update DB_PATH in this script.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        existing = get_existing_columns(conn)
        print(f"Existing columns: {sorted(existing)}")

        if 'email_verified' not in existing:
            print("Adding email_verified column (default=0/False)...")
            conn.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0")
        else:
            print("email_verified already exists, skipping")

        if 'email_verification_token' not in existing:
            print("Adding email_verification_token column...")
            conn.execute("ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(128)")
        else:
            print("email_verification_token already exists, skipping")

        if 'email_verification_sent_at' not in existing:
            print("Adding email_verification_sent_at column...")
            conn.execute("ALTER TABLE users ADD COLUMN email_verification_sent_at DATETIME")
        else:
            print("email_verification_sent_at already exists, skipping")

        # Mark existing admin users as verified
        conn.execute("UPDATE users SET email_verified = 1 WHERE is_admin = 1")

        conn.commit()
        print("\nMigration complete!")

        # Verify
        updated = get_existing_columns(conn)
        print(f"Updated columns: {sorted(updated)}")
    finally:
        conn.close()


if __name__ == '__main__':
    migrate()
