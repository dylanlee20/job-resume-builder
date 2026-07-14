"""SessionRecord model — a logged coaching/mentoring session.

Submitted from the admin User Management page's Session History panel.
"""
from datetime import datetime

from models.database import db

SESSION_TYPES = ("Technical", "Behavioral", "Competition", "Interview Prep", "Referral")

# Session lifecycle: a mentor logs a 'pending' session; the student approves
# (-> 'approved', which counts toward their progress) or rejects it.
SESSION_STATUSES = ("pending", "approved", "rejected")


class SessionRecord(db.Model):
    __tablename__ = "session_records"

    id = db.Column(db.Integer, primary_key=True)
    # Optional link to the student (a User row). Kept nullable so a session can
    # be logged before the student exists in the roster.
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # Who logged the session. mentor_id links to the mentor's User row;
    # mentor_name is kept as a display fallback (and for legacy admin-logged rows).
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    mentor_name = db.Column(db.String(120), nullable=False)

    session_type = db.Column(db.String(40), nullable=False)
    topic = db.Column(db.Text, nullable=True)
    # Mentor-entered duration in hours (drives payroll).
    hours = db.Column(db.Numeric(5, 2), nullable=True)

    # Approval workflow.
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    # Filled by the STUDENT at approval time.
    rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    feedback = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    student = db.relationship(
        "User", foreign_keys=[student_id],
        backref=db.backref("session_records", lazy="dynamic"),
    )
    mentor = db.relationship(
        "User", foreign_keys=[mentor_id],
        backref=db.backref("mentor_sessions", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<SessionRecord {self.id} {self.session_type} by {self.mentor_name} [{self.status}]>"

    @property
    def stars(self) -> str:
        """Filled/empty star glyphs for display."""
        r = self.rating or 0
        return "★" * r + "☆" * (5 - r)
