"""Weekly Job Snapshot Model - For Historical Tracking"""
from datetime import datetime
from models.database import db


class JobSnapshot(db.Model):
    """Weekly snapshot of job market statistics"""
    __tablename__ = 'job_snapshots'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Snapshot metadata
    snapshot_date = db.Column(db.DateTime, nullable=False, index=True)
    week_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False, index=True)

    # Overall statistics
    total_active_jobs = db.Column(db.Integer, nullable=False)
    total_companies = db.Column(db.Integer, nullable=False)
    total_locations = db.Column(db.Integer, nullable=False)

    # Category breakdown (JSON stored as text)
    category_breakdown = db.Column(db.Text, nullable=True)
    company_breakdown = db.Column(db.Text, nullable=True)
    location_breakdown = db.Column(db.Text, nullable=True)

    # Growth metrics
    new_jobs_this_week = db.Column(db.Integer, nullable=True)
    closed_jobs_this_week = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<JobSnapshot {self.snapshot_date.strftime("%Y-W%W")} - {self.total_active_jobs} jobs>'
