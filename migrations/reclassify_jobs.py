"""
Migration: Reclassify all jobs using the updated AI-proof classification logic.

Fixes:
- Case sensitivity bug (M&A, ECM, DCM, etc. never matched)
- Software engineering jobs mislabeled as Sales & Trading
- Overly broad keywords (trading, solutions, structuring)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask
from models.database import db
from models.job import Job
from utils.ai_proof_filter import classify_ai_proof_role
from utils.seniority_classifier import classify_job_type
from config import Config


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
        skipped = 0
        changes = {'promoted': [], 'demoted': [], 'recategorized': []}

        for job in jobs:
            old_ai_proof = job.is_ai_proof
            old_category = job.ai_proof_category

            is_ai_proof, category = classify_ai_proof_role(
                job.title,
                job.description or ''
            )

            # Also reclassify job type (Internship vs Full Time)
            new_job_type = classify_job_type(job.title, job.description or '')
            if job.seniority != new_job_type:
                job.seniority = new_job_type

            if is_ai_proof == old_ai_proof and category == old_category:
                skipped += 1
                continue

            # Track the change type
            if not old_ai_proof and is_ai_proof:
                changes['promoted'].append(f"  + {job.company}: {job.title} [{old_category} → {category}]")
            elif old_ai_proof and not is_ai_proof:
                changes['demoted'].append(f"  - {job.company}: {job.title} [{old_category} → EXCLUDED]")
            else:
                changes['recategorized'].append(f"  ~ {job.company}: {job.title} [{old_category} → {category}]")

            job.is_ai_proof = is_ai_proof
            job.ai_proof_category = category
            updated += 1

        db.session.commit()

        print(f"\nReclassification complete: {updated} changed, {skipped} unchanged")

        if changes['promoted']:
            print(f"\nNewly AI-Proof ({len(changes['promoted'])}):")
            for c in changes['promoted']:
                print(c)

        if changes['demoted']:
            print(f"\nDemoted to EXCLUDED ({len(changes['demoted'])}):")
            for c in changes['demoted']:
                print(c)

        if changes['recategorized']:
            print(f"\nRecategorized ({len(changes['recategorized'])}):")
            for c in changes['recategorized']:
                print(c)


if __name__ == '__main__':
    run_migration()
