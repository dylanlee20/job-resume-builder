"""MentorRate — an effective-dated hourly pay rate for a mentor.

A mentor's pay rate can change over time. Each change closes the previous row
(sets effective_to) and opens a new one. The rate that applies to a session is
the row whose window contains the session's created_at.
"""
from datetime import datetime

from models.database import db


class MentorRate(db.Model):
    __tablename__ = "mentor_rates"

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")

    # [effective_from, effective_to) — effective_to NULL means "current".
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    effective_to = db.Column(db.DateTime, nullable=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    mentor = db.relationship("User", backref=db.backref("rates", lazy="dynamic"))

    def __repr__(self):
        return f"<MentorRate mentor={self.mentor_id} {self.hourly_rate} {self.currency}>"

    @classmethod
    def effective_at(cls, mentor_id: int, when: datetime):
        """The rate row in force for a mentor at a given instant, or None."""
        return (
            cls.query.filter(
                cls.mentor_id == mentor_id,
                cls.effective_from <= when,
                db.or_(cls.effective_to.is_(None), cls.effective_to > when),
            )
            .order_by(cls.effective_from.desc())
            .first()
        )
