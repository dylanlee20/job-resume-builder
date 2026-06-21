"""Migration: create the session_records table.

db.create_all() only creates tables that don't yet exist, so this is safe to
re-run and leaves existing tables untouched.
"""
from migrations._dbapp import create_db_app
from models.database import db
from models.session_record import SessionRecord  # noqa: F401  (ensures table is registered)


def migrate():
    app = create_db_app()
    with app.app_context():
        db.create_all()
        print("OK: session_records table ensured.")


if __name__ == "__main__":
    migrate()
