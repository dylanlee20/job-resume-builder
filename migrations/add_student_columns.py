"""Migration: add student-roster profile columns to the users table.

Adds college, major, graduation_year, sessions, is_done, offers.
Idempotent — checks existing columns first, so it is safe to re-run.
Works on both SQLite (prod) and Postgres.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import inspect, text

from migrations._dbapp import create_db_app
from models.database import db

# column name -> SQL type clause used in ALTER TABLE ADD COLUMN
NEW_COLUMNS = {
    "college": "VARCHAR(120)",
    "major": "VARCHAR(200)",
    "graduation_year": "INTEGER",
    "sessions": "VARCHAR(40)",
    "is_done": "BOOLEAN NOT NULL DEFAULT 0",
    "offers": "VARCHAR(255)",
    "full_name": "VARCHAR(120)",
    "member_no": "VARCHAR(6)",
}


def migrate():
    app = create_db_app()
    with app.app_context():
        existing = {c["name"] for c in inspect(db.engine).get_columns("users")}
        added = []
        for name, type_clause in NEW_COLUMNS.items():
            if name in existing:
                continue
            db.session.execute(text(f"ALTER TABLE users ADD COLUMN {name} {type_clause}"))
            added.append(name)
        db.session.commit()
        if added:
            print(f"OK: Added columns to users: {', '.join(added)}")
        else:
            print("OK: Student columns already present — nothing to do.")


if __name__ == "__main__":
    migrate()
