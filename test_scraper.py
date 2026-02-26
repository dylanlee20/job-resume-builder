"""Quick test to run one scraper and populate some jobs"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from models.database import db
from models.job import Job
from utils.ai_proof_filter import classify_ai_proof_role
from config import Config

# Import one scraper for testing
from scrapers.goldman_scraper import GoldmanSachsScraper

def create_app():
    """Create Flask app for database access"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def save_job_to_db(job_data):
    """Save a job to database with AI-proof classification"""
    try:
        # Check if job already exists
        existing_job = Job.query.filter_by(job_url=job_data['job_url']).first()
        if existing_job:
            return (False, 'duplicate')

        # Classify job
        is_ai_proof, category = classify_ai_proof_role(
            job_data['title'],
            job_data.get('description', '')
        )

        # Create new job
        job = Job(
            company=job_data['company'],
            title=job_data['title'],
            location=job_data['location'],
            description=job_data.get('description', ''),
            post_date=job_data.get('post_date'),
            deadline=job_data.get('deadline'),
            source_website=job_data['source_website'],
            job_url=job_data['job_url'],
            is_ai_proof=is_ai_proof,
            ai_proof_category=category,
            status='active',
            is_new=True
        )

        db.session.add(job)
        db.session.commit()
        return (True, category)

    except Exception as e:
        print(f"Error saving job: {e}")
        db.session.rollback()
        return (False, f'error: {e}')

if __name__ == '__main__':
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("Running Goldman Sachs scraper (test)")
        print("=" * 80)

        scraper = GoldmanSachsScraper()
        jobs = scraper.scrape_with_retry()

        print(f"\nScraped {len(jobs)} jobs")
        print(f"Saving to database with AI-proof classification...\n")

        ai_proof_count = 0
        excluded_count = 0
        duplicate_count = 0

        for job_data in jobs:
            saved, reason = save_job_to_db(job_data)
            if saved:
                if reason in ['Investment Banking', 'Sales & Trading', 'Asset & Wealth Management',
                             'Risk Management', 'Private Equity', 'Structuring']:
                    ai_proof_count += 1
                    print(f"✓ AI-PROOF [{reason}]: {job_data['title'][:60]}")
                else:
                    excluded_count += 1
                    print(f"✗ EXCLUDED [{reason}]: {job_data['title'][:60]}")
            else:
                if reason == 'duplicate':
                    duplicate_count += 1

        print("\n" + "=" * 80)
        print(f"SUMMARY")
        print("=" * 80)
        print(f"Total scraped: {len(jobs)}")
        print(f"AI-proof jobs: {ai_proof_count}")
        print(f"Excluded jobs: {excluded_count}")
        print(f"Duplicates: {duplicate_count}")
        print("=" * 80)
