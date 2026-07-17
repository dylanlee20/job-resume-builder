"""Regression tests for admin user deletion with FK-linked dependents.

A mentor's users row is referenced by mentor_rates / mentor_payouts /
mentor_students / session_records under PRAGMA foreign_keys=ON. Deleting such
an account used to raise IntegrityError, which the global 500 handler swallowed
with a rollback + redirect, so the delete silently did nothing. These tests
lock in that a fully-wired mentor can be deleted and that session history is
preserved (the link is nulled, the row is kept).
"""
from datetime import datetime
from decimal import Decimal

import pytest

from models.database import db
from models.user import User, generate_portal_code
from models.session_record import SessionRecord
from models.mentor_rate import MentorRate
from models.mentor_payout import MentorPayout
from models.mentor_student import MentorStudent


ADMIN_USER, ADMIN_PW = "adm", "password123"


def _mk(username, **kw):
    fields = dict(status="active", email_verified=True)
    fields.update(kw)
    u = User(username=username, email=f"{username}@x.com",
             portal_code=generate_portal_code(), **fields)
    u.set_password("password123")
    db.session.add(u)
    db.session.commit()
    return u


def _login_admin(client):
    return client.post("/auth/login", data={"username": ADMIN_USER, "password": ADMIN_PW})


@pytest.fixture()
def wired_mentor(app, db):
    """A mentor with a rate, a payout, a logged session, and a linked student."""
    with app.app_context():
        _mk(ADMIN_USER, is_admin=True)
        m = _mk("lilyw", is_mentor=True, full_name="Lily W", payout_currency="CNY")
        s = _mk("stu", total_sessions=10)
        db.session.add(MentorRate(mentor_id=m.id, hourly_rate=Decimal("100"),
                                  currency="CNY", effective_from=datetime(1970, 1, 1)))
        db.session.add(MentorPayout(mentor_id=m.id, week_start=datetime(2026, 1, 5),
                                    week_end=datetime(2026, 1, 11), amount=Decimal("200"),
                                    currency="CNY"))
        db.session.add(MentorStudent(mentor_id=m.id, student_id=s.id))
        db.session.add(SessionRecord(student_id=s.id, mentor_id=m.id, mentor_name="Lily W",
                                     session_type="Technical", hours=Decimal("2"),
                                     status="approved", approved_at=datetime.utcnow()))
        db.session.commit()
        return m.id, s.id


def test_delete_mentor_with_dependents_succeeds(app, db, client, wired_mentor):
    mentor_id, _ = wired_mentor
    _login_admin(client)
    client.post(f"/admin/users/{mentor_id}/delete", follow_redirects=True)
    with app.app_context():
        assert User.query.get(mentor_id) is None
        assert MentorRate.query.filter_by(mentor_id=mentor_id).count() == 0
        assert MentorPayout.query.filter_by(mentor_id=mentor_id).count() == 0
        assert MentorStudent.query.filter_by(mentor_id=mentor_id).count() == 0


def test_delete_preserves_session_history(app, db, client, wired_mentor):
    mentor_id, student_id = wired_mentor
    _login_admin(client)
    client.post(f"/admin/users/{mentor_id}/delete", follow_redirects=True)
    with app.app_context():
        # The session row survives with the mentor link nulled and the name
        # snapshot intact; the student's approved-hours count is untouched.
        rec = SessionRecord.query.filter_by(student_id=student_id).one()
        assert rec.mentor_id is None
        assert rec.mentor_name == "Lily W"
        assert rec.status == "approved"


def test_admin_cannot_delete_self(app, db, client):
    with app.app_context():
        admin = _mk(ADMIN_USER, is_admin=True)
        admin_id = admin.id
    _login_admin(client)
    client.post(f"/admin/users/{admin_id}/delete", follow_redirects=True)
    with app.app_context():
        assert User.query.get(admin_id) is not None
