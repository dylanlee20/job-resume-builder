"""Migration to add scraper_runs table"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from models.database import db
from models.scraper_run import ScraperRun


def migrate():
    """Add scraper_runs table"""
    app, _ = create_app()

    with app.app_context():
        print("Creating scraper_runs table...")
        db.create_all()
        print("✓ scraper_runs table created successfully!")


if __name__ == '__main__':
    migrate()
