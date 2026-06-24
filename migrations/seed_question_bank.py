"""Migration: create question_bank_entries table and seed the starter image.

The seed image ships in the repo at data/seed_question_bank/ so it reaches the
cloud server on deploy. It is copied into uploads/question_bank/ (which persists
across deploys) and a QuestionBankEntry row is created. Idempotent by title.
"""
import os
import shutil

from migrations._dbapp import create_db_app
from models.database import db
from models.question_bank import QuestionBankEntry

_ROOT = os.path.dirname(os.path.dirname(__file__))
SEED_DIR = os.path.join(_ROOT, "data", "seed_question_bank")
UPLOAD_DIR = os.path.join(_ROOT, "uploads", "question_bank")

# (title, student, program_round, seed filename)
SEED_ENTRIES = [
    (
        "JPM Interview Questions (SPD / Insight / Superday)",
        "JPM NYC / JP Morgan NY",
        "SPD · Insight Program · Superday",
        "jpm-interview-questions.png",
    ),
]


def migrate():
    app = create_db_app()
    with app.app_context():
        db.create_all()  # creates question_bank_entries if missing
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        created = 0
        for title, student, program_round, fname in SEED_ENTRIES:
            if QuestionBankEntry.query.filter_by(title=title).first():
                continue
            src = os.path.join(SEED_DIR, fname)
            if not os.path.isfile(src):
                print(f"WARN: seed image missing, skipping: {src}")
                continue
            dst = os.path.join(UPLOAD_DIR, fname)
            if not os.path.isfile(dst):
                shutil.copyfile(src, dst)
            db.session.add(QuestionBankEntry(
                title=title,
                student=student,
                program_round=program_round,
                original_filename=fname,
                stored_filename=fname,
                uploaded_by="seed",
            ))
            created += 1
        db.session.commit()
        print(f"OK: Question bank seeded: {created} created.")


if __name__ == "__main__":
    migrate()
