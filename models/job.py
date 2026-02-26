"""Job model with AI-proof categorization"""
from datetime import datetime
from models.database import db
from sqlalchemy import Index
import hashlib


class Job(db.Model):
    """Job model with AI-proof category tracking"""
    __tablename__ = 'jobs'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Unique identifier (for deduplication)
    job_hash = db.Column(db.String(32), unique=True, nullable=False, index=True)

    # Basic information
    company = db.Column(db.String(100), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=True, index=True)
    industry = db.Column(db.String(100), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    description_hash = db.Column(db.String(32), nullable=True)

    # AI-Proof categorization (NEW)
    ai_proof_category = db.Column(db.String(50), nullable=True, index=True)
    is_ai_proof = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Job type classification
    seniority = db.Column(db.String(20), nullable=True, index=True)  # 'Internship' or 'Full Time'

    # Date information
    post_date = db.Column(db.DateTime, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)

    # Source information
    source_website = db.Column(db.String(200), nullable=False)
    job_url = db.Column(db.String(500), nullable=False)

    # Status tracking
    status = db.Column(db.String(20), default='active', nullable=False, index=True)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # User interaction fields
    is_important = db.Column(db.Boolean, default=False, nullable=False, index=True)
    user_notes = db.Column(db.Text, nullable=True)
    
    # Application tracking (NEW)
    submitted = db.Column(db.Boolean, default=False, nullable=False)
    application_date = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Create composite indexes (improve query performance)
    __table_args__ = (
        Index('idx_company_location', 'company', 'location'),
        Index('idx_status_first_seen', 'status', 'first_seen'),
        Index('idx_ai_proof_category', 'is_ai_proof', 'ai_proof_category'),
    )

    @property
    def is_new(self):
        """Check if this is a new job (within 7 days)"""
        return (datetime.utcnow() - self.first_seen).days < 7

    @property
    def is_updated(self):
        """Check if recently updated (within 3 days)"""
        return (datetime.utcnow() - self.last_updated).days < 3

    @staticmethod
    def generate_job_hash(company, title, location):
        """Generate unique job hash for deduplication"""
        data = f"{company}{title}{location}".lower().strip()
        return hashlib.md5(data.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_description_hash(description):
        """Generate description hash"""
        if not description:
            return None
        return hashlib.md5(description.encode('utf-8')).hexdigest()

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'company': self.company,
            'title': self.title,
            'location': self.location,
            'category': self.category,
            'industry': self.industry,
            'ai_proof_category': self.ai_proof_category,
            'is_ai_proof': self.is_ai_proof,
            'description': self.description,
            'post_date': self.post_date.isoformat() if self.post_date else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'source_website': self.source_website,
            'job_url': self.job_url,
            'status': self.status,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'is_new': self.is_new,
            'is_updated': self.is_updated,
            'is_important': self.is_important,
            'user_notes': self.user_notes,
            'submitted': self.submitted,
            'application_date': self.application_date.isoformat() if self.application_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        ai_flag = "✓" if self.is_ai_proof else "✗"
        return f'<Job {self.company} - {self.title} [AI-Proof: {ai_flag}]>'
