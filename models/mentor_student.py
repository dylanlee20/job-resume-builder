"""MentorStudent — a mentor's remembered link to a student.

A mentor only ever sees students they have linked. The first link is created
by proving knowledge of the student's User ID (portal_code) + name; afterwards
the student appears in the mentor's dropdown for easy logging.
"""
from datetime import datetime

from models.database import db


class MentorStudent(db.Model):
    __tablename__ = "mentor_students"
    __table_args__ = (
        db.UniqueConstraint("mentor_id", "student_id", name="uq_mentor_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    mentor = db.relationship("User", foreign_keys=[mentor_id],
                             backref=db.backref("linked_students", lazy="dynamic"))
    student = db.relationship("User", foreign_keys=[student_id],
                              backref=db.backref("linked_mentors", lazy="dynamic"))

    def __repr__(self):
        return f"<MentorStudent mentor={self.mentor_id} student={self.student_id}>"
