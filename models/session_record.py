"""SessionRecord model — a logged coaching/mentoring session.

Submitted from the admin User Management page's Session History panel.
"""
from datetime import datetime

from models.database import db

SESSION_TYPES = ("Technicals", "Behav", "Mock", "Project")


class SessionRecord(db.Model):
    __tablename__ = "session_records"

    id = db.Column(db.Integer, primary_key=True)
    # Optional link to the student (a User row). Kept nullable so a session can
    # be logged before the student exists in the roster.
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    mentor_name = db.Column(db.String(120), nullable=False)
    session_type = db.Column(db.String(40), nullable=False)
    topic = db.Column(db.String(255), nullable=True)
    # 1-5 star rating.
    rating = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    student = db.relationship("User", backref=db.backref("session_records", lazy="dynamic"))

    def __repr__(self):
        return f"<SessionRecord {self.id} {self.session_type} by {self.mentor_name}>"

    @property
    def stars(self) -> str:
        """Filled/empty star glyphs for display."""
        r = self.rating or 0
        return "★" * r + "☆" * (5 - r)
