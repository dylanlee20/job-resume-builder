"""Resume assessment model for AI-powered analysis"""
from datetime import datetime
from models.database import db
import json


class ResumeAssessment(db.Model):
    """Resume assessment results from LLM analysis"""
    __tablename__ = 'resume_assessments'

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Assessment results
    overall_score = db.Column(db.Integer, nullable=False)  # 0-100
    strengths = db.Column(db.Text, nullable=False)  # JSON array of strings
    weaknesses = db.Column(db.Text, nullable=False)  # JSON array of strings
    industry_compatibility = db.Column(db.Text, nullable=False)  # JSON object: {industry: score}
    detailed_feedback = db.Column(db.Text, nullable=False)  # Full LLM response
    
    # Assessment metadata
    assessment_type = db.Column(db.String(20), default='free', nullable=False)  # 'free' or 'premium'
    model_used = db.Column(db.String(50), nullable=True)  # e.g., 'gpt-4o-mini'
    tokens_used = db.Column(db.Integer, nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    resume = db.relationship('Resume', back_populates='assessments')
    user = db.relationship('User', back_populates='assessments')

    def get_strengths(self):
        """Parse strengths from JSON (immutable pattern)"""
        try:
            return json.loads(self.strengths) if self.strengths else []
        except json.JSONDecodeError:
            return []
    
    def set_strengths(self, strengths_list):
        """Store strengths as JSON (immutable pattern)"""
        self.strengths = json.dumps(strengths_list)
    
    def get_weaknesses(self):
        """Parse weaknesses from JSON (immutable pattern)"""
        try:
            return json.loads(self.weaknesses) if self.weaknesses else []
        except json.JSONDecodeError:
            return []
    
    def set_weaknesses(self, weaknesses_list):
        """Store weaknesses as JSON (immutable pattern)"""
        self.weaknesses = json.dumps(weaknesses_list)
    
    def get_industry_compatibility(self):
        """Parse industry compatibility from JSON (immutable pattern)"""
        try:
            return json.loads(self.industry_compatibility) if self.industry_compatibility else {}
        except json.JSONDecodeError:
            return {}
    
    def set_industry_compatibility(self, compatibility_dict):
        """Store industry compatibility as JSON (immutable pattern)"""
        self.industry_compatibility = json.dumps(compatibility_dict)

    def to_dict(self):
        """Convert to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'resume_id': self.resume_id,
            'user_id': self.user_id,
            'overall_score': self.overall_score,
            'strengths': self.get_strengths(),
            'weaknesses': self.get_weaknesses(),
            'industry_compatibility': self.get_industry_compatibility(),
            'detailed_feedback': self.detailed_feedback,
            'assessment_type': self.assessment_type,
            'model_used': self.model_used,
            'tokens_used': self.tokens_used,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<ResumeAssessment {self.id} - Score: {self.overall_score}/100>'
