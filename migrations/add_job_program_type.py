"""Migration: add jobs.program_type and backfill it by classifying titles.

Idempotent — adds the column only if missing, and only fills rows where
program_type is still NULL.
"""
from sqlalchemy import inspect, text

from migrations._dbapp import create_db_app
from models.database import db
from models.job import Job
from services.program_classifier import classify_program


def migrate():
    app = create_db_app()
    with app.app_context():
        cols = {c["name"] for c in inspect(db.engine).get_columns("jobs")}
        if "program_type" not in cols:
            db.session.execute(text("ALTER TABLE jobs ADD COLUMN program_type VARCHAR(20)"))
            db.session.commit()
            print("OK: Added jobs.program_type column.")
        else:
            print("OK: jobs.program_type already present.")

        tagged = 0
        for job in Job.query.filter(Job.program_type.is_(None)).all():
            pt = classify_program(job.title, job.description or "")
            if pt:
                job.program_type = pt
                tagged += 1
        if tagged:
            db.session.commit()
        print(f"OK: Tagged {tagged} existing jobs as early/diversity programs.")


if __name__ == "__main__":
    migrate()
