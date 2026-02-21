"""ScraperRun model for tracking scraper execution history"""
from datetime import datetime
from models.database import db
import json


class ScraperRun(db.Model):
    """Tracks each scraper execution with status and results"""
    __tablename__ = 'scraper_runs'

    id = db.Column(db.Integer, primary_key=True)

    # Run identification
    run_id = db.Column(db.String(36), unique=True, nullable=False, index=True)  # UUID
    scraper_name = db.Column(db.String(100), nullable=False, index=True)  # e.g. 'eFinancialCareers'
    trigger = db.Column(db.String(20), default='manual', nullable=False)  # 'manual' or 'scheduled'

    # Status tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    # Status values: 'pending', 'running', 'completed', 'failed', 'cancelled'

    # Timing
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)

    # Results
    jobs_found = db.Column(db.Integer, default=0, nullable=False)
    jobs_new = db.Column(db.Integer, default=0, nullable=False)
    jobs_updated = db.Column(db.Integer, default=0, nullable=False)
    jobs_skipped = db.Column(db.Integer, default=0, nullable=False)

    # Logs and errors
    log_output = db.Column(db.Text, nullable=True)  # Accumulated log lines
    error_message = db.Column(db.Text, nullable=True)

    # Config snapshot
    config_snapshot = db.Column(db.Text, nullable=True)  # JSON of scraper config used

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def append_log(self, line):
        """Append a log line to log_output"""
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        entry = f"[{timestamp}] {line}"
        if self.log_output:
            self.log_output = self.log_output + '\n' + entry
        else:
            self.log_output = entry

    def get_log_lines(self):
        """Return log lines as a list"""
        if not self.log_output:
            return []
        return self.log_output.split('\n')

    def get_duration_display(self):
        """Human-readable duration"""
        if self.duration_seconds is None:
            return 'N/A'
        if self.duration_seconds < 60:
            return f"{self.duration_seconds:.1f}s"
        minutes = int(self.duration_seconds // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{minutes}m {seconds}s"

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'run_id': self.run_id,
            'scraper_name': self.scraper_name,
            'trigger': self.trigger,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'duration_display': self.get_duration_display(),
            'jobs_found': self.jobs_found,
            'jobs_new': self.jobs_new,
            'jobs_updated': self.jobs_updated,
            'jobs_skipped': self.jobs_skipped,
            'error_message': self.error_message,
            'log_lines': self.get_log_lines(),
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<ScraperRun {self.run_id[:8]}... [{self.scraper_name}] {self.status}>'
