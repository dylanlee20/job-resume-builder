"""Migration to recreate scraper_runs table with correct schema.

Run this on the VPS after pulling the fixes:
    cd ~/job-resume-builder
    python3 migrations/fix_scraper_runs.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from models.database import db
from sqlalchemy import text


def migrate():
    """Drop and recreate scraper_runs table with correct schema"""
    app, _ = create_app()

    with app.app_context():
        print("Dropping old scraper_runs table...")
        db.session.execute(text("DROP TABLE IF EXISTS scraper_runs"))
        db.session.commit()
        print("Recreating with correct schema...")
        db.create_all()
        print("Done! scraper_runs table recreated.")


if __name__ == '__main__':
    migrate()
