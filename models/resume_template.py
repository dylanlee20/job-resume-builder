"""Resume template model for admin-uploaded successful resumes"""
from datetime import datetime
from models.database import db
import json


class ResumeTemplate(db.Model):
    """Successful resume templates uploaded by admin"""
    __tablename__ = 'resume_templates'

    id = db.Column(db.Integer, primary_key=True)
    
    # Classification
    industry = db.Column(db.String(100), nullable=False, index=True)
    company = db.Column(db.String(100), nullable=True)
    role_level = db.Column(db.String(50), nullable=True)  # 'Analyst', 'Associate', etc.
    
    # File information
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True, index=True)
    file_path = db.Column(db.String(500), nullable=False)
    
    # Extracted content
    extracted_text = db.Column(db.Text, nullable=True)
    key_elements = db.Column(db.Text, nullable=True)  # JSON: extracted success patterns
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Metadata
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)  # Admin notes about this template

    def get_key_elements(self):
        """Parse key elements from JSON (immutable pattern)"""
        try:
            return json.loads(self.key_elements) if self.key_elements else {}
        except json.JSONDecodeError:
            return {}
    
    def set_key_elements(self, elements_dict):
        """Store key elements as JSON (immutable pattern)"""
        self.key_elements = json.dumps(elements_dict)

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'industry': self.industry,
            'company': self.company,
            'role_level': self.role_level,
            'original_filename': self.original_filename,
            'is_active': self.is_active,
            'uploaded_at': self.uploaded_at.isoformat(),
            'notes': self.notes,
            'key_elements': self.get_key_elements(),
        }

    def __repr__(self):
        active = "✓" if self.is_active else "✗"
        return f'<ResumeTemplate {self.industry} - {self.company} [{active}]>'
