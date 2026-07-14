"""Migration: mentor/student roles, portal IDs, session approval, payroll.

Adds:
  * users:           is_mentor, portal_code (+unique index), allowed_curriculums,
                     payout_currency, total_sessions
  * session_records: mentor_id, hours, status, approved_at
  * new tables:      mentor_rates, student_payments, mentor_payouts

Backfills a unique 5-digit portal_code for every existing account and marks
pre-existing (admin-logged) sessions as 'approved' so they keep counting toward
student progress. Idempotent and safe on both SQLite (prod-MVP) and MySQL.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import inspect, text

from migrations._dbapp import create_db_app
from models.database import db
import models  # noqa: F401  registers every model (needed for create_all)

USERS_COLUMNS = {
    "is_mentor": "BOOLEAN NOT NULL DEFAULT 0",
    "portal_code": "VARCHAR(5)",
    "allowed_curriculums": "VARCHAR(160) NOT NULL DEFAULT ''",
    "payout_currency": "VARCHAR(3) NOT NULL DEFAULT 'USD'",
    "total_sessions": "INTEGER",
    "exchange_rate": "DECIMAL(12,6)",
}

SESSION_COLUMNS = {
    "mentor_id": "INTEGER",
    "hours": "DECIMAL(5,2)",
    "status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
    "approved_at": "DATETIME",
}


def _add_missing(table: str, columns: dict) -> list:
    existing = {c["name"] for c in inspect(db.engine).get_columns(table)}
    added = []
    for name, clause in columns.items():
        if name in existing:
            continue
        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {clause}"))
        added.append(name)
    db.session.commit()
    return added


def _backfill_portal_codes() -> int:
    rows = db.session.execute(
        text("SELECT id, portal_code FROM users")
    ).fetchall()
    used = {r[1] for r in rows if r[1]}
    n = 0
    for uid, code in rows:
        if code:
            continue
        new = str(random.randint(10000, 99999))
        while new in used:
            new = str(random.randint(10000, 99999))
        used.add(new)
        db.session.execute(
            text("UPDATE users SET portal_code = :c WHERE id = :i"),
            {"c": new, "i": uid},
        )
        n += 1
    db.session.commit()
    return n


def _ensure_portal_code_unique_index() -> None:
    insp = inspect(db.engine)
    names = {ix["name"] for ix in insp.get_indexes("users")}
    if "ux_users_portal_code" in names:
        return
    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX ux_users_portal_code ON users (portal_code)"
        ))
        db.session.commit()
    except Exception as exc:  # pragma: no cover - dialect/index-exists variance
        db.session.rollback()
        print(f"   (portal_code unique index not created: {exc})")


def migrate():
    app = create_db_app()
    with app.app_context():
        # 1. New tables (mentor_rates, student_payments, mentor_payouts).
        db.create_all()

        # 2. New columns on existing tables.
        u_added = _add_missing("users", USERS_COLUMNS)
        s_added = _add_missing("session_records", SESSION_COLUMNS)

        # 3. Legacy sessions (logged before the approval workflow) count as
        #    approved. Only run when the status column was just introduced.
        if "status" in s_added:
            db.session.execute(text(
                "UPDATE session_records SET status = 'approved' WHERE status = 'pending'"
            ))
            db.session.commit()

        # 4. Unique 5-digit portal_code for every account + unique index.
        filled = _backfill_portal_codes()
        _ensure_portal_code_unique_index()

        parts = []
        if u_added:
            parts.append(f"users +{', '.join(u_added)}")
        if s_added:
            parts.append(f"session_records +{', '.join(s_added)}")
        parts.append(f"portal_codes backfilled: {filled}")
        print("OK: " + "; ".join(parts))


if __name__ == "__main__":
    migrate()
