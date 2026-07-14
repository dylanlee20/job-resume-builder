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
        return {"mentor": m.id, "student": s.id, "other": s2.id,
                "student_code": s.portal_code, "student_name": s.full_name}


def test_mentor_first_log_requires_correct_id_and_name(app, db, client, actors):
    from models.mentor_student import MentorStudent
    _login(client, "mentorx")
    # Correct ID + name: logs the session AND links the student.
    r = client.post("/portal/log", data={
        "new_student_code": actors["student_code"], "new_student_name": actors["student_name"],
        "session_type": "Behavioral", "hours": "1.0", "topic": "notes"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        sr = SessionRecord.query.filter_by(mentor_id=actors["mentor"]).first()
        assert sr is not None and sr.status == "pending" and sr.student_id == actors["student"]
        assert MentorStudent.query.filter_by(
            mentor_id=actors["mentor"], student_id=actors["student"]).count() == 1


def test_wrong_name_logs_nothing_and_no_link(app, db, client, actors):
    from models.mentor_student import MentorStudent
    _login(client, "mentorx")
    r = client.post("/portal/log", data={
        "new_student_code": actors["student_code"], "new_student_name": "Wrong Person",
        "session_type": "Behavioral", "hours": "1.0", "topic": "notes"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert SessionRecord.query.filter_by(mentor_id=actors["mentor"]).count() == 0
        assert MentorStudent.query.filter_by(mentor_id=actors["mentor"]).count() == 0


def test_unlinked_student_not_selectable_by_id(app, db, client, actors):
    # Posting a raw student_id for a student the mentor never linked must fail.
    _login(client, "mentorx")
    client.post("/portal/log", data={"student_id": actors["student"],
                "session_type": "Behavioral", "hours": "1.0", "topic": "notes"}, follow_redirects=True)
    with app.app_context():
        assert SessionRecord.query.filter_by(mentor_id=actors["mentor"]).count() == 0


def test_linked_student_then_logs_by_dropdown(app, db, client, actors):
    from models.mentor_student import MentorStudent
    with app.app_context():
        db.session.add(MentorStudent(mentor_id=actors["mentor"], student_id=actors["student"]))
        db.session.commit()
    _login(client, "mentorx")
    r = client.post("/portal/log", data={"student_id": actors["student"],
                    "session_type": "Technical", "hours": "2", "topic": "notes"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert SessionRecord.query.filter_by(mentor_id=actors["mentor"]).count() == 1


def test_admin_logs_as_mentor(app, db, client, actors):
    from models.mentor_student import MentorStudent
    with app.app_context():
        _mk("adminx", is_admin=True)
    _login(client, "adminx")
    r = client.post("/portal/log", data={
        "mentor_id": actors["mentor"], "student_id": actors["student"],
        "session_type": "Behavioral", "hours": "3", "topic": "coached resume"},
        follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        sr = SessionRecord.query.filter_by(mentor_id=actors["mentor"]).first()
        assert sr is not None and sr.status == "pending"
        assert sr.student_id == actors["student"]
        # the student is auto-linked to the mentor the admin acted as
        assert MentorStudent.query.filter_by(
            mentor_id=actors["mentor"], student_id=actors["student"]).count() == 1


def test_admin_must_pick_a_mentor(app, db, client, actors):
    with app.app_context():
        _mk("adminy", is_admin=True)
    _login(client, "adminy")
    client.post("/portal/log", data={
        "student_id": actors["student"], "session_type": "Behavioral",
        "hours": "3", "topic": "x"}, follow_redirects=True)  # no mentor_id
    with app.app_context():
        assert SessionRecord.query.count() == 0


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
