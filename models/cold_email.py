"""Cold email outreach models"""
from datetime import datetime
from models.database import db
import json


class EmailCampaign(db.Model):
    """Email campaign for cold outreach"""
    __tablename__ = 'email_campaigns'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Campaign details
    name = db.Column(db.String(200), nullable=False)
    subject_template = db.Column(db.String(500), nullable=False)
    body_template = db.Column(db.Text, nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'), nullable=True)

    # Stats
    total_sent = db.Column(db.Integer, default=0)
    total_opened = db.Column(db.Integer, default=0)
    total_replied = db.Column(db.Integer, default=0)

    # Status
    status = db.Column(db.String(20), default='draft', nullable=False)
    # Status values: 'draft', 'active', 'paused', 'completed'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('campaigns', lazy='dynamic', cascade='all, delete-orphan'))
    resume = db.relationship('Resume', backref='campaigns')
    recipients = db.relationship('EmailRecipient', back_populates='campaign', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subject_template': self.subject_template,
            'status': self.status,
            'total_sent': self.total_sent,
            'total_opened': self.total_opened,
            'total_replied': self.total_replied,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<EmailCampaign {self.id} - {self.name}>'


class EmailRecipient(db.Model):
    """Individual recipient in a campaign"""
    __tablename__ = 'email_recipients'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('email_campaigns.id'), nullable=False, index=True)

    # Recipient info
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(200), nullable=True)
    company = db.Column(db.String(200), nullable=True)
    title = db.Column(db.String(200), nullable=True)

    # Tracking
    status = db.Column(db.String(20), default='pending', nullable=False)
    # Status values: 'pending', 'sent', 'opened', 'replied', 'bounced', 'failed'
    sent_at = db.Column(db.DateTime, nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)

    # Tracking pixel ID
    tracking_id = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    campaign = db.relationship('EmailCampaign', back_populates='recipients')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'company': self.company,
            'title': self.title,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
        }

    def __repr__(self):
        return f'<EmailRecipient {self.id} - {self.email} [{self.status}]>'
