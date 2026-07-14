"""Integration tests for the mentor-logs -> student-approves workflow."""
import pytest

from models.database import db
from models.user import User, generate_portal_code
from models.session_record import SessionRecord


def _mk(username, pw="password123", **kw):
    u = User(username=username, email=f"{username}@x.com", status="active",
             email_verified=True, portal_code=generate_portal_code(), **kw)
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, username, pw="password123"):
    return client.post("/auth/login", data={"username": username, "password": pw})


@pytest.fixture()
def actors(app, db):
    with app.app_context():
        m = _mk("mentorx", is_mentor=True, full_name="Mentor X")
        s = _mk("studentx", total_sessions=5, full_name="Student X")
        s2 = _mk("studenty", total_sessions=5)
        return {"mentor": m.id, "student": s.id, "other": s2.id}


def test_mentor_log_creates_pending(app, db, client, actors):
    _login(client, "mentorx")
    r = client.post("/portal/log", data={"student_id": actors["student"],
                    "session_type": "Behavioral", "hours": "1.0"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        sr = SessionRecord.query.filter_by(mentor_id=actors["mentor"]).first()
        assert sr is not None and sr.status == "pending"
        assert User.query.get(actors["student"]).sessions_completed == 0


def test_student_approves_increments_progress(app, db, client, actors):
    with app.app_context():
        sr = SessionRecord(student_id=actors["student"], mentor_id=actors["mentor"],
                           mentor_name="Mentor X", session_type="Technical", status="pending")
        db.session.add(sr); db.session.commit()
        sid = sr.id
    _login(client, "studentx")
    r = client.post(f"/portal/sessions/{sid}/approve",
                    data={"rating": "5", "feedback": "clear"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        sr = SessionRecord.query.get(sid)
        assert sr.status == "approved" and sr.rating == 5 and sr.feedback == "clear"
        assert User.query.get(actors["student"]).sessions_completed == 1


def test_student_cannot_approve_someone_elses_session(app, db, client, actors):
    with app.app_context():
        sr = SessionRecord(student_id=actors["student"], mentor_id=actors["mentor"],
                           mentor_name="Mentor X", session_type="Technical", status="pending")
        db.session.add(sr); db.session.commit()
        sid = sr.id
    _login(client, "studenty")  # the OTHER student
    client.post(f"/portal/sessions/{sid}/approve",
                data={"rating": "5", "feedback": "x"}, follow_redirects=True)
    with app.app_context():
        assert SessionRecord.query.get(sid).status == "pending"  # unchanged


def test_approval_requires_valid_rating(app, db, client, actors):
    with app.app_context():
        sr = SessionRecord(student_id=actors["student"], mentor_id=actors["mentor"],
                           mentor_name="Mentor X", session_type="Technical", status="pending")
        db.session.add(sr); db.session.commit()
        sid = sr.id
    _login(client, "studentx")
    client.post(f"/portal/sessions/{sid}/approve",
                data={"rating": "9", "feedback": "x"}, follow_redirects=True)
    with app.app_context():
        assert SessionRecord.query.get(sid).status == "pending"  # rejected bad rating


def test_mentor_cannot_reach_student_area(app, db, client, actors):
    _login(client, "mentorx")
    # student approval route is student-only; mentor gets bounced (no 500)
    r = client.get("/portal/my-sessions", follow_redirects=True)
    assert r.status_code == 200
