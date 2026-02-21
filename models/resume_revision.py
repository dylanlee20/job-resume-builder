"""Resume revision model for paid template-based suggestions"""
from datetime import datetime
from models.database import db
import json


class ResumeRevision(db.Model):
    """Paid resume revision results using successful templates"""
    __tablename__ = 'resume_revisions'

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'), nullable=False, index=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('resume_assessments.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Revision parameters
    target_industry = db.Column(db.String(100), nullable=False, index=True)
    templates_used = db.Column(db.Text, nullable=False)  # JSON: list of template IDs
    
    # Revision results
    revision_suggestions = db.Column(db.Text, nullable=False)  # Full revision output
    before_score = db.Column(db.Integer, nullable=True)
    projected_after_score = db.Column(db.Integer, nullable=True)
    
    # LLM metadata
    model_used = db.Column(db.String(50), nullable=True)
    tokens_used = db.Column(db.Integer, nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    resume = db.relationship('Resume', back_populates='revisions')

    def get_templates_used(self):
        """Parse templates used from JSON (immutable pattern)"""
        try:
            return json.loads(self.templates_used) if self.templates_used else []
        except json.JSONDecodeError:
            return []
    
    def set_templates_used(self, template_ids):
        """Store template IDs as JSON (immutable pattern)"""
        self.templates_used = json.dumps(template_ids)

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'resume_id': self.resume_id,
            'assessment_id': self.assessment_id,
            'user_id': self.user_id,
            'target_industry': self.target_industry,
            'templates_used': self.get_templates_used(),
            'revision_suggestions': self.revision_suggestions,
            'before_score': self.before_score,
            'projected_after_score': self.projected_after_score,
            'model_used': self.model_used,
            'tokens_used': self.tokens_used,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        score_change = f"{self.before_score}→{self.projected_after_score}" if self.before_score else "N/A"
        return f'<ResumeRevision {self.id} - {self.target_industry} [{score_change}]>'
