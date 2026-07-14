"""MentorPayout — a snapshot of one mentor's issued salary for one week.

Created when the admin issues weekly salary from the reconciliation report.
Persisting it prevents double-paying: issuing is idempotent per
(mentor_id, week_start). Amount is the mentor-currency total; amount_usd is the
reconciled figure using fx_to_usd captured at issuance.
"""
from datetime import datetime

from models.database import db


class MentorPayout(db.Model):
    __tablename__ = "mentor_payouts"
    __table_args__ = (
        db.UniqueConstraint("mentor_id", "week_start", name="uq_mentor_week"),
    )

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Mon 00:00 .. next Mon 00:00 (UTC), the reconciliation week.
    week_start = db.Column(db.DateTime, nullable=False, index=True)
    week_end = db.Column(db.DateTime, nullable=False)

    total_hours = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    session_count = db.Column(db.Integer, nullable=False, default=0)

    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)   # mentor currency
    currency = db.Column(db.String(3), nullable=False, default="USD")
    # USD/CNY rate (local currency per USD). amount_usd = amount / fx_to_usd; USD uses 1.
    fx_to_usd = db.Column(db.Numeric(12, 6), nullable=False, default=1)
    amount_usd = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default="issued")
    issued_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    mentor = db.relationship("User", backref=db.backref("payouts", lazy="dynamic"))

    def __repr__(self):
        return f"<MentorPayout mentor={self.mentor_id} week={self.week_start:%Y-%m-%d} {self.amount} {self.currency}>"
