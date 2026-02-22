"""Migration to add progress tracking columns to scraper_runs.

Run on VPS:
    cd ~/job-resume-builder
    source venv/bin/activate
    python3 migrations/add_scraper_run_progress.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from models.database import db
from sqlalchemy import text


def migrate():
    app, _ = create_app()

    with app.app_context():
        # Add total_companies column (safe: IF NOT EXISTS not supported in SQLite ALTER TABLE,
        # so we catch the error if column already exists)
        for col, col_type, default in [
            ('total_companies', 'INTEGER', '0'),
            ('current_company', 'VARCHAR(100)', 'NULL'),
        ]:
            try:
                db.session.execute(text(
                    f"ALTER TABLE scraper_runs ADD COLUMN {col} {col_type} DEFAULT {default}"
                ))
                db.session.commit()
                print(f"Added column: {col}")
            except Exception as e:
                db.session.rollback()
                if 'duplicate column' in str(e).lower():
                    print(f"Column {col} already exists, skipping.")
                else:
                    print(f"Warning adding {col}: {e}")

        print("Migration complete.")


if __name__ == '__main__':
    migrate()
