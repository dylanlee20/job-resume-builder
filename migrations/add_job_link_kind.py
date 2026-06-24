"""Migration: add jobs.link_kind ('direct' application page vs 'site' landing)."""
from sqlalchemy import inspect, text

from migrations._dbapp import create_db_app
from models.database import db


def migrate():
    app = create_db_app()
    with app.app_context():
        cols = {c["name"] for c in inspect(db.engine).get_columns("jobs")}
        if "link_kind" not in cols:
            db.session.execute(text("ALTER TABLE jobs ADD COLUMN link_kind VARCHAR(10)"))
            db.session.commit()
            print("OK: Added jobs.link_kind column.")
        else:
            print("OK: jobs.link_kind already present.")


if __name__ == "__main__":
    migrate()
