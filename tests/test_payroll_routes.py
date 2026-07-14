"""Integration tests for admin payroll issuance edge cases."""
from datetime import datetime
from decimal import Decimal

import pytest

from models.database import db
from models.user import User, generate_portal_code
from models.session_record import SessionRecord
from models.mentor_rate import MentorRate
from models.mentor_payout import MentorPayout


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


def _this_monday():
    now = datetime.utcnow()
    return (now - __import__("datetime").timedelta(days=now.weekday())).strftime("%Y-%m-%d")


@pytest.fixture()
def week_setup(app, db):
    """A non-USD mentor with an approved 2h session this week + a rate."""
    with app.app_context():
        _mk(ADMIN_USER, is_admin=True)  # a fresh admin (the auto-created one is dropped per test)
        m = _mk("mtr", is_mentor=True, full_name="Mtr", payout_currency="CNY")
        s = _mk("stu", total_sessions=10)
        db.session.add(MentorRate(mentor_id=m.id, hourly_rate=Decimal("100"),
                                  currency="CNY", effective_from=datetime(1970, 1, 1)))
        db.session.add(SessionRecord(student_id=s.id, mentor_id=m.id, mentor_name="Mtr",
                                     session_type="Technical", hours=Decimal("2"),
                                     status="approved", approved_at=datetime.utcnow()))
        db.session.commit()
        return m.id


def _login_admin(client):
    return client.post("/auth/login", data={"username": ADMIN_USER, "password": ADMIN_PW})


def test_issue_skips_non_usd_without_fx(app, db, client, week_setup):
    _login_admin(client)
    monday = _this_monday()
    # No fx_<id> supplied -> the non-USD mentor must be skipped, not paid at 1:1.
    client.post("/admin/reconciliation/issue", data={"week_start": monday}, follow_redirects=True)
    with app.app_context():
        assert MentorPayout.query.filter_by(mentor_id=week_setup).count() == 0


def test_issue_with_fx_then_idempotent(app, db, client, week_setup):
    _login_admin(client)
    monday = _this_monday()
    client.post("/admin/reconciliation/issue",
                data={"week_start": monday, f"fx_{week_setup}": "0.14"}, follow_redirects=True)
    with app.app_context():
        payouts = MentorPayout.query.filter_by(mentor_id=week_setup).all()
        assert len(payouts) == 1
        # 2h * 100 CNY = 200 CNY; * 0.14 = 28.00 USD
        assert payouts[0].amount == Decimal("200.00")
        assert payouts[0].amount_usd == Decimal("28.00")
    # Re-issue the same week must not create a second payout.
    client.post("/admin/reconciliation/issue",
                data={"week_start": monday, f"fx_{week_setup}": "0.14"}, follow_redirects=True)
    with app.app_context():
        assert MentorPayout.query.filter_by(mentor_id=week_setup).count() == 1
