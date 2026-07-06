"""SavedQuestion model — a student's bookmarked question-bank problem.

One row per (user, deck, question). Stores the slide range of the question
unit (question slide through last solution slide) so the saved-questions page
can deep-link both the problem and its worked solution even if the deck is
re-rendered with the same layout.
"""
from datetime import datetime

from models.database import db


class SavedQuestion(db.Model):
    __tablename__ = "saved_questions"
    __table_args__ = (
        db.UniqueConstraint("user_id", "deck_slug", "question_key",
                            name="uq_saved_question_user_deck_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    deck_slug = db.Column(db.String(120), nullable=False)
    question_key = db.Column(db.String(20), nullable=False)

    # Denormalized from toc.json at save time for cheap list rendering.
    label = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(200), nullable=True)
    question_slide = db.Column(db.Integer, nullable=False)
    answer_slide = db.Column(db.Integer, nullable=True)
    end_slide = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<SavedQuestion u{self.user_id} {self.deck_slug}#{self.question_key}>"
