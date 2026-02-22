"""
Migration: Re-normalize all job locations in the database.

Applies the updated normalize_location() function to every job,
fixing issues like "2 locations", duplicate city variants, etc.
Also updates job_hash to match the new normalized location.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask
from models.database import db
from models.job import Job
from utils.job_utils import normalize_location
from config import Config
from sqlalchemy.exc import IntegrityError

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def run_migration():
    app = create_app()
    with app.app_context():
        jobs = Job.query.all()
        updated = 0
        merged = 0
        skipped = 0

        for job in jobs:
            old_location = job.location
            new_location = normalize_location(old_location)

            if old_location == new_location:
                skipped += 1
                continue

            # Recompute job hash with the new normalized location
            new_hash = Job.generate_job_hash(job.company, job.title, new_location)

            # Check if a job with the new hash already exists (would be a duplicate)
            existing = Job.query.filter_by(job_hash=new_hash).first()
            if existing and existing.id != job.id:
                # This job is a duplicate after normalization — delete it
                db.session.delete(job)
                merged += 1
                continue

            job.location = new_location
            job.job_hash = new_hash
            updated += 1

        db.session.commit()
        print(f"Migration complete: {updated} updated, {merged} duplicates removed, {skipped} unchanged")

if __name__ == '__main__':
    run_migration()
