"""ScraperRun model to track scraper execution history"""
from datetime import datetime
from models.database import db
from sqlalchemy import Index


class ScraperRun(db.Model):
    """Track each scraper run with results and errors"""
    __tablename__ = 'scraper_runs'

    id = db.Column(db.Integer, primary_key=True)

    # Timing
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)

    # Status
    status = db.Column(db.String(20), nullable=False, default='running')  # running, completed, failed
    trigger = db.Column(db.String(50), nullable=False)  # 'manual', 'scheduled', 'automatic'

    # Results
    total_jobs_scraped = db.Column(db.Integer, default=0)
    new_jobs_added = db.Column(db.Integer, default=0)
    jobs_updated = db.Column(db.Integer, default=0)
    companies_scraped = db.Column(db.Integer, default=0)
    companies_failed = db.Column(db.Integer, default=0)

    # Logs
    error_log = db.Column(db.Text, nullable=True)
    company_results = db.Column(db.Text, nullable=True)  # JSON of per-company results

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_scraper_run_status', 'status', 'started_at'),
    )

    @property
    def is_running(self):
        """Check if scraper is currently running"""
        return self.status == 'running'

    @property
    def is_completed(self):
        """Check if scraper completed successfully"""
        return self.status == 'completed'

    @property
    def is_failed(self):
        """Check if scraper failed"""
        return self.status == 'failed'

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
        """Convert to dictionary"""
        return {
            'id': self.id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'duration_display': self.get_duration_display(),
            'status': self.status,
            'trigger': self.trigger,
            'total_jobs_scraped': self.total_jobs_scraped,
            'new_jobs_added': self.new_jobs_added,
            'jobs_updated': self.jobs_updated,
            'companies_scraped': self.companies_scraped,
            'companies_failed': self.companies_failed,
            'error_log': self.error_log,
            'company_results': self.company_results,
        }

    def __repr__(self):
        return f'<ScraperRun {self.id} - {self.status} - {self.started_at}>'
