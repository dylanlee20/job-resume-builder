"""Coffee chat mentorship marketplace models."""
from datetime import datetime

from models.database import db


class MentorProfile(db.Model):
    """Mentor profile shown in the coffee chat marketplace."""
    __tablename__ = 'mentor_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)

    # Public profile
    name = db.Column(db.String(120), nullable=False)
    headline = db.Column(db.String(200), nullable=True)
    industry = db.Column(db.String(120), nullable=False, index=True)
    role = db.Column(db.String(120), nullable=False, index=True)
    company = db.Column(db.String(120), nullable=True, index=True)
    years_experience = db.Column(db.Integer, nullable=False, default=0)
    timezone = db.Column(db.String(64), nullable=False, default='UTC')
    hourly_rate = db.Column(db.Integer, nullable=True)  # cents
    coffee_chat_price = db.Column(db.Integer, nullable=False, default=2500)  # cents
    bio = db.Column(db.Text, nullable=True)
    linkedin_url = db.Column(db.String(255), nullable=True)
    profile_photo = db.Column(db.String(500), nullable=True)

    # Verification / compliance
    verified_status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    compliance_accepted = db.Column(db.Boolean, nullable=False, default=False)
    employer_policy_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    confidentiality_confirmed = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('mentor_profile', uselist=False))
    availabilities = db.relationship(
        'MentorAvailability',
        back_populates='mentor',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    bookings = db.relationship(
        'CoffeeChatBooking',
        back_populates='mentor',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    @property
    def is_listable(self):
        """True when mentor is allowed to be publicly listed for bookings."""
        return (
            self.verified_status in ('self_attested', 'verified')
            and self.compliance_accepted
            and self.employer_policy_confirmed
            and self.confidentiality_confirmed
        )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'headline': self.headline,
            'industry': self.industry,
            'role': self.role,
            'company': self.company,
            'years_experience': self.years_experience,
            'timezone': self.timezone,
            'hourly_rate': self.hourly_rate,
            'coffee_chat_price': self.coffee_chat_price,
            'bio': self.bio,
            'linkedin_url': self.linkedin_url,
            'profile_photo': self.profile_photo,
            'verified_status': self.verified_status,
            'compliance_accepted': self.compliance_accepted,
            'employer_policy_confirmed': self.employer_policy_confirmed,
            'confidentiality_confirmed': self.confidentiality_confirmed,
            'is_listable': self.is_listable,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class MentorAvailability(db.Model):
    """Recurring weekly availability window for a mentor."""
    __tablename__ = 'mentor_availability'

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('mentor_profiles.id'), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False, index=True)  # 0=Mon, 6=Sun
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    mentor = db.relationship('MentorProfile', back_populates='availabilities')

    __table_args__ = (
        db.Index('idx_mentor_day_window', 'mentor_id', 'day_of_week', 'start_time'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'mentor_id': self.mentor_id,
            'day_of_week': self.day_of_week,
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
        }


class CoffeeChatBooking(db.Model):
    """Coffee chat booking between a student and mentor."""
    __tablename__ = 'coffee_chat_bookings'

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('mentor_profiles.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Stored in UTC
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    mentor_timezone = db.Column(db.String(64), nullable=False)
    student_timezone = db.Column(db.String(64), nullable=False, default='UTC')

    # Booking lifecycle
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    # pending | confirmed | completed | cancelled
    student_disclaimer_accepted = db.Column(db.Boolean, nullable=False, default=False)
    liability_notice_seen = db.Column(db.Boolean, nullable=False, default=False)

    # Economics
    price_cents = db.Column(db.Integer, nullable=False)
    platform_fee_cents = db.Column(db.Integer, nullable=False)
    mentor_payout_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='usd')

    # Milestones
    confirmed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    reminder_sent_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    mentor = db.relationship('MentorProfile', back_populates='bookings')
    student = db.relationship('User', backref=db.backref('coffee_chat_bookings', lazy='dynamic'))
    payment = db.relationship('CoffeeChatPayment', back_populates='booking', uselist=False, cascade='all, delete-orphan')
    meeting_link = db.relationship('MeetingLink', back_populates='booking', uselist=False, cascade='all, delete-orphan')
    notes = db.relationship('MentorshipNote', back_populates='booking', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_mentor_booking_status', 'mentor_id', 'status', 'start_time'),
        db.Index('idx_student_booking_status', 'student_id', 'status', 'start_time'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'mentor_id': self.mentor_id,
            'student_id': self.student_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'mentor_timezone': self.mentor_timezone,
            'student_timezone': self.student_timezone,
            'status': self.status,
            'student_disclaimer_accepted': self.student_disclaimer_accepted,
            'liability_notice_seen': self.liability_notice_seen,
            'price_cents': self.price_cents,
            'platform_fee_cents': self.platform_fee_cents,
            'mentor_payout_cents': self.mentor_payout_cents,
            'currency': self.currency,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'meeting_url': self.meeting_link.meeting_url if self.meeting_link else None,
        }


class CoffeeChatPayment(db.Model):
    """Payment audit record for a coffee chat booking."""
    __tablename__ = 'coffee_chat_payments'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('coffee_chat_bookings.id'), nullable=False, unique=True, index=True)
    stripe_checkout_session_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True, unique=True, index=True)

    amount_cents = db.Column(db.Integer, nullable=False)
    platform_fee_cents = db.Column(db.Integer, nullable=False)
    mentor_payout_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='usd')
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    # pending | succeeded | failed | refunded

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    booking = db.relationship('CoffeeChatBooking', back_populates='payment')

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'stripe_checkout_session_id': self.stripe_checkout_session_id,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'amount_cents': self.amount_cents,
            'platform_fee_cents': self.platform_fee_cents,
            'mentor_payout_cents': self.mentor_payout_cents,
            'currency': self.currency,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MeetingLink(db.Model):
    """Meeting link generated for a confirmed booking."""
    __tablename__ = 'meeting_links'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('coffee_chat_bookings.id'), nullable=False, unique=True, index=True)
    provider = db.Column(db.String(32), nullable=False, default='internal')
    meeting_url = db.Column(db.String(500), nullable=False)
    meeting_token = db.Column(db.String(128), nullable=True, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    booking = db.relationship('CoffeeChatBooking', back_populates='meeting_link')

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'provider': self.provider,
            'meeting_url': self.meeting_url,
            'meeting_token': self.meeting_token,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MentorshipNote(db.Model):
    """Post-session notes linked to mentorship + application tracker context."""
    __tablename__ = 'mentorship_notes'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('coffee_chat_bookings.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True, index=True)

    notes = db.Column(db.Text, nullable=True)
    advice_received = db.Column(db.Text, nullable=True)
    next_steps = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    booking = db.relationship('CoffeeChatBooking', back_populates='notes')
    student = db.relationship('User', backref=db.backref('mentorship_notes', lazy='dynamic'))
    job = db.relationship('Job', backref=db.backref('mentorship_notes', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_notes_student_job', 'student_id', 'job_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'student_id': self.student_id,
            'job_id': self.job_id,
            'notes': self.notes,
            'advice_received': self.advice_received,
            'next_steps': self.next_steps,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
