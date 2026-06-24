"""QuestionBankEntry model — an uploaded interview question-bank image.

Managed from the admin portal. The stored file lives under
uploads/question_bank/; it is served watermarked (viewer email + IP + EST).
"""
from datetime import datetime

from models.database import db


class QuestionBankEntry(db.Model):
    __tablename__ = "question_bank_entries"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    # Optional context columns matching the source sheet.
    student = db.Column(db.String(120), nullable=True)
    program_round = db.Column(db.String(120), nullable=True)

    original_filename = db.Column(db.String(255), nullable=True)
    stored_filename = db.Column(db.String(255), nullable=False)

    uploaded_by = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<QuestionBankEntry {self.id} {self.title!r}>"
