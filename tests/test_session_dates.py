"""Tests for the optional session-date field on the log-a-session forms."""
from datetime import datetime
from decimal import Decimal

import pytest

from models.database import db
from models.user import User, generate_portal_code
from models.session_record import SessionRecord
from models.mentor_student import MentorStudent
from utils.session_dates import parse_session_date


NOW = datetime(2026, 7, 17, 9, 30, 0)


class TestParseSessionDate:
    def test_blank_defaults_to_now(self):
        assert parse_session_date("", NOW) == (NOW, None)
        assert parse_session_date(None, NOW) == (NOW, None)

    def test_valid_past_date_becomes_noon(self):
        dt, err = parse_session_date("2026-07-10", NOW)
        assert err is None
        assert dt == datetime(2026, 7, 10, 12, 0, 0)

    def test_today_is_allowed(self):
        dt, err = parse_session_date("2026-07-17", NOW)
        assert err is None and dt.date() == NOW.date()

    def test_future_date_rejected(self):
        dt, err = parse_session_date("2026-07-18", NOW)
        assert dt is None and "future" in err.lower()

    def test_malformed_rejected(self):
        for bad in ("not-a-date", "2026/07/10", "07-10-2026", "2026-13-01"):
            dt, err = parse_session_date(bad, NOW)
            assert dt is None and err


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


def test_admin_create_session_honours_date(app, db, client):
    with app.app_context():
        _mk(ADMIN_USER, is_admin=True)
        sid = _mk("stu").id
    client.post("/auth/login", data={"username": ADMIN_USER, "password": ADMIN_PW})
    client.post("/admin/sessions/create", data={
        "student_id": sid, "mentor_name": "Mtr", "session_type": "Technical",
        "topic": "APV", "session_date": "2026-07-10",
    }, follow_redirects=True)
    with app.app_context():
        rec = SessionRecord.query.filter_by(student_id=sid).one()
        assert rec.created_at.date() == datetime(2026, 7, 10).date()


def test_portal_log_session_honours_date(app, db, client):
    with app.app_context():
        m = _mk("mtr", is_mentor=True, full_name="Mtr")
        s = _mk("stu2")
        db.session.add(MentorStudent(mentor_id=m.id, student_id=s.id))
        db.session.commit()
        sid = s.id
    client.post("/auth/login", data={"username": "mtr", "password": "password123"})
    client.post("/portal/log", data={
        "student_id": sid, "session_type": "Technical", "hours": "1.5",
        "topic": "Comps walk-through", "session_date": "2026-07-08",
    }, follow_redirects=True)
    with app.app_context():
        rec = SessionRecord.query.filter_by(student_id=sid).one()
        assert rec.created_at.date() == datetime(2026, 7, 8).date()
        assert rec.status == "pending"
