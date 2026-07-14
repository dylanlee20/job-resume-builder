"""Unit tests for mentor/student roles, portal IDs, and payroll math."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from models.database import db
from models.user import User, generate_portal_code
from models.session_record import SessionRecord
from models.mentor_rate import MentorRate
from models.student_payment import StudentPayment


def _mk(username, **kw):
    fields = dict(status="active", email_verified=True)
    fields.update(kw)
    u = User(username=username, email=f"{username}@x.com",
             portal_code=generate_portal_code(), **fields)
    u.set_password("password123")
    db.session.add(u)
    db.session.commit()
    return u


class TestPortalCode:
    def test_generated_5_digits_and_unique(self, app, db):
        with app.app_context():
            codes = {generate_portal_code() for _ in range(20)}
            for c in codes:
                assert len(c) == 5 and c.isdigit()

    def test_generator_avoids_existing(self, app, db):
        with app.app_context():
            u = _mk("m")
            assert generate_portal_code() != u.portal_code


class TestCurriculumAccess:
    def test_mentor_gated_to_allowed(self, app, db):
        with app.app_context():
            m = _mk("mentor", is_mentor=True)
            m.set_allowed_curriculums(["05-quant", "bogus", "08-consulting"])
            assert m.allowed_curriculums == "05-quant,08-consulting"
            assert m.has_curriculum("05-quant") is True
            assert m.has_curriculum("02-technical-generalist") is False

    def test_student_and_admin_never_gated(self, app, db):
        with app.app_context():
            s = _mk("stu")
            a = _mk("adm", is_admin=True)
            assert s.has_curriculum("08-consulting") is True
            assert a.has_curriculum("08-consulting") is True

    def test_frozen_mentor_denied(self, app, db):
        with app.app_context():
            m = _mk("mz", is_mentor=True, status="frozen")
            m.set_allowed_curriculums(["05-quant"])
            assert m.has_curriculum("05-quant") is False


class TestProgress:
    def test_progress_counts_only_approved(self, app, db):
        with app.app_context():
            s = _mk("stud", total_sessions=10)
            db.session.add_all([
                SessionRecord(student_id=s.id, mentor_name="M", session_type="Technical", status="approved"),
                SessionRecord(student_id=s.id, mentor_name="M", session_type="Technical", status="approved"),
                SessionRecord(student_id=s.id, mentor_name="M", session_type="Technical", status="pending"),
                SessionRecord(student_id=s.id, mentor_name="M", session_type="Technical", status="rejected"),
            ])
            db.session.commit()
            assert s.sessions_completed == 2
            assert s.progress_display == "2/10"
            assert s.sessions_pct == 20


class TestEffectiveRate:
    def test_rate_lookup_by_date(self, app, db):
        with app.app_context():
            m = _mk("mr", is_mentor=True)
            t0 = datetime(2026, 1, 1)
            t1 = datetime(2026, 6, 1)
            db.session.add_all([
                MentorRate(mentor_id=m.id, hourly_rate=Decimal("40"), currency="USD",
                           effective_from=t0, effective_to=t1),
                MentorRate(mentor_id=m.id, hourly_rate=Decimal("60"), currency="USD",
                           effective_from=t1, effective_to=None),
            ])
            db.session.commit()
            assert MentorRate.effective_at(m.id, datetime(2026, 3, 1)).hourly_rate == Decimal("40")
            assert MentorRate.effective_at(m.id, datetime(2026, 7, 1)).hourly_rate == Decimal("60")
            assert MentorRate.effective_at(m.id, datetime(2025, 1, 1)) is None


class TestPaymentUsd:
    def test_recompute_usd(self, app, db):
        with app.app_context():
            s = _mk("sp")
            # USD/CNY = CNY per USD; USD = amount / rate. 1000 CNY / 8 = 125.
            p = StudentPayment(student_id=s.id, amount=Decimal("1000"),
                               currency="CNY", fx_to_usd=Decimal("8"))
            p.recompute_usd()
            assert p.amount_usd == Decimal("125.00")
