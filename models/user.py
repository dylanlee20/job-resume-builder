"""User model with subscription tier support"""
from models.database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class User(UserMixin, db.Model):
    """User model for authentication and subscription management"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Subscription fields
    tier = db.Column(db.String(20), default='free', nullable=False)  # 'free' or 'premium'
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    resumes = db.relationship('Resume', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    assessments = db.relationship('ResumeAssessment', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set the password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches"""
        return check_password_hash(self.password_hash, password)
    
    def is_premium(self):
        """Check if user has premium tier"""
        return self.tier == 'premium'
    
    def upgrade_to_premium(self):
        """Upgrade user to premium tier"""
        self.tier = 'premium'
        return self
    
    def downgrade_to_free(self):
        """Downgrade user to free tier"""
        self.tier = 'free'
        return self
    
    def to_dict(self):
        """Convert user to dictionary (immutable pattern)"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'tier': self.tier,
            'stripe_customer_id': self.stripe_customer_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self):
        return f'<User {self.username} ({self.tier})>'


def create_admin_user(username='admin', password='admin123', email='admin@newwhale.com'):
    """Create default admin user if not exists"""
    existing = User.query.filter_by(username=username).first()
    if not existing:
        admin = User(
            username=username,
            email=email,
            is_admin=True,
            tier='premium'  # Admin gets premium by default
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        logger.info(f"Admin user '{username}' created successfully!")
        return admin
    else:
        logger.info(f"Admin user '{username}' already exists")
    return existing
