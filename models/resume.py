"""Resume model for user uploads"""
from datetime import datetime
from models.database import db
import json


class Resume(db.Model):
    """Resume upload model"""
    __tablename__ = 'resumes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # File information
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True, index=True)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    file_type = db.Column(db.String(10), nullable=False)  # 'pdf' or 'docx'
    
    # Extracted content
    extracted_text = db.Column(db.Text, nullable=True)
    
    # Processing status
    status = db.Column(db.String(20), default='uploaded', nullable=False, index=True)
    # Status values: 'uploaded', 'parsed', 'assessed', 'error'
    
    # Timestamps
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    parsed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', back_populates='resumes')
    assessments = db.relationship('ResumeAssessment', back_populates='resume', lazy='dynamic', cascade='all, delete-orphan')
    revisions = db.relationship('ResumeRevision', back_populates='resume', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'status': self.status,
            'uploaded_at': self.uploaded_at.isoformat(),
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None,
            'has_text': bool(self.extracted_text),
        }

    def __repr__(self):
        return f'<Resume {self.id} - {self.original_filename} ({self.status})>'
