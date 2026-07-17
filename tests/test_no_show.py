"""Tests for the 'No Show' session type — always logged as a fixed 0.5 hrs."""
from decimal import Decimal

import pytest

from models.database import db
from models.user import User, generate_portal_code
from models.session_record import (
    SessionRecord, SESSION_TYPES, NO_SHOW_TYPE, NO_SHOW_HOURS,
)
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


def test_no_show_is_a_session_type():
    assert NO_SHOW_TYPE in SESSION_TYPES
    assert NO_SHOW_HOURS == Decimal("0.5")


def test_portal_no_show_forces_half_hour_without_hours(app, db, client):
    with app.app_context():
        m = _mk("mtr", is_mentor=True, full_name="Mtr")
        s = _mk("stu")
        db.session.add(MentorStudent(mentor_id=m.id, student_id=s.id))
        db.session.commit()
        sid = s.id
    client.post("/auth/login", data={"username": "mtr", "password": "password123"})
    # No hours entered — a normal type would fail, but No Show is accepted.
    client.post("/portal/log", data={
        "student_id": sid, "session_type": NO_SHOW_TYPE,
        "topic": "Student did not attend", "hours": "",
    }, follow_redirects=True)
    with app.app_context():
        rec = SessionRecord.query.filter_by(student_id=sid).one()
        assert rec.session_type == NO_SHOW_TYPE
        assert rec.hours == Decimal("0.5")


def test_portal_no_show_ignores_entered_hours(app, db, client):
    with app.app_context():
        m = _mk("mtr", is_mentor=True, full_name="Mtr")
        s = _mk("stu")
        db.session.add(MentorStudent(mentor_id=m.id, student_id=s.id))
        db.session.commit()
        sid = s.id
    client.post("/auth/login", data={"username": "mtr", "password": "password123"})
    client.post("/portal/log", data={
        "student_id": sid, "session_type": NO_SHOW_TYPE,
        "topic": "no show", "hours": "3",  # tampered value must be ignored
    }, follow_redirects=True)
    with app.app_context():
        assert SessionRecord.query.filter_by(student_id=sid).one().hours == Decimal("0.5")


def test_admin_no_show_sets_half_hour(app, db, client):
    with app.app_context():
        _mk(ADMIN_USER, is_admin=True)
        sid = _mk("stu").id
    client.post("/auth/login", data={"username": ADMIN_USER, "password": ADMIN_PW})
    client.post("/admin/sessions/create", data={
        "student_id": sid, "mentor_name": "Mtr", "session_type": NO_SHOW_TYPE,
        "topic": "no show",
    }, follow_redirects=True)
    with app.app_context():
        rec = SessionRecord.query.filter_by(student_id=sid).one()
        assert rec.session_type == NO_SHOW_TYPE
        assert rec.hours == Decimal("0.5")
