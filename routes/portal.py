"""Portal blueprint: mentor session logging + student approval.

Role-aware pages living under /portal:
  * mentors log sessions (pending) and watch their approval status
  * students approve/reject sessions, rate + give feedback, and see progress
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models.database import db
from models.user import User
from models.session_record import SessionRecord, SESSION_TYPES
from models.mentor_student import MentorStudent
from utils.auth_decorators import mentor_required, student_required

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


def _linked_students(mentor):
    """Students this mentor has been linked to, sorted by name."""
    students = [ln.student for ln in
                MentorStudent.query.filter_by(mentor_id=mentor.id).all() if ln.student]
    return sorted(students, key=lambda u: (u.full_name or u.username).lower())


def _match_and_link(mentor, code, name):
    """Verify a student by User ID + name and link them to the mentor.

    Returns the student on success (creating the link if new), else None.
    A wrong ID and a wrong name are indistinguishable to the caller, so a
    mentor cannot enumerate students they don't already know.
    """
    code = (code or "").strip()
    provided = (name or "").strip().lower()
    if not code or not provided:
        return None
    student = User.query.filter_by(
        portal_code=code, is_admin=False, is_mentor=False).first()
    if student is None:
        return None
    # Require BOTH the User ID (above) and the student's actual name to match.
    # Name is matched case-insensitively; fall back to username only when no
    # real name is on file.
    name_on_file = (student.full_name or student.username or "").strip().lower()
    if provided != name_on_file:
        return None
    if not MentorStudent.query.filter_by(mentor_id=mentor.id, student_id=student.id).first():
        db.session.add(MentorStudent(mentor_id=mentor.id, student_id=student.id))
    return student


@portal_bp.route("/")
@login_required
def home():
    """Role-aware landing page."""
    if current_user.is_mentor:
        return redirect(url_for("portal.mentor_sessions"))
    if not current_user.is_admin:
        return redirect(url_for("portal.student_sessions"))
    # Admins have their own tooling; send them to user management.
    return redirect(url_for("admin.users"))


# ---- Mentor ---------------------------------------------------------------

@portal_bp.route("/log", methods=["GET", "POST"])
@mentor_required
def log_session():
    students = _linked_students(current_user)
    if request.method == "POST":
        session_type = (request.form.get("session_type", "") or "").strip()
        topic = (request.form.get("topic", "") or "").strip()
        hours_raw = (request.form.get("hours", "") or "").strip()
        new_code = (request.form.get("new_student_code", "") or "").strip()
        new_name = (request.form.get("new_student_name", "") or "").strip()

        errors = []
        # Resolve the student. Adding a new one requires the correct ID + name;
        # otherwise it must be one already linked to this mentor.
        student = None
        if new_code or new_name:
            student = _match_and_link(current_user, new_code, new_name)
            if student is None:
                errors.append("No student matches that User ID and name. "
                              "Ask the student to confirm both, exactly.")
        else:
            sid = request.form.get("student_id", type=int)
            student = next((s for s in students if s.id == sid), None)
            if student is None:
                errors.append("Choose one of your students, or add a new one "
                              "by their User ID and name.")

        if session_type not in SESSION_TYPES:
            errors.append("Pick a valid session type.")
        if not topic:
            errors.append("Enter what the session covered (topic / notes).")
        hours = None
        try:
            hours = Decimal(hours_raw)
            if hours <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            errors.append("Enter the session length in hours (e.g. 1.5).")

        if errors:
            db.session.rollback()  # drop any half-made link if validation failed
            for e in errors:
                flash(e, "danger")
            return render_template("portal/log_session.html",
                                   students=students, session_types=SESSION_TYPES)

        db.session.add(SessionRecord(
            student_id=student.id,
            mentor_id=current_user.id,
            mentor_name=current_user.full_name or current_user.username,
            session_type=session_type,
            topic=topic,
            hours=hours,
            status="pending",
        ))
        db.session.commit()  # commits the session AND any new mentor-student link
        flash(f"Session logged for {student.full_name or student.username} "
              f"— awaiting their approval.", "success")
        return redirect(url_for("portal.mentor_sessions"))

    return render_template("portal/log_session.html",
                           students=students, session_types=SESSION_TYPES)


@portal_bp.route("/sessions")
@mentor_required
def mentor_sessions():
    rows = (SessionRecord.query
            .filter_by(mentor_id=current_user.id)
            .order_by(SessionRecord.created_at.desc())
            .all())
    return render_template("portal/mentor_sessions.html", sessions=rows)


# ---- Student --------------------------------------------------------------

@portal_bp.route("/my-sessions")
@student_required
def student_sessions():
    pending = (SessionRecord.query
               .filter_by(student_id=current_user.id, status="pending")
               .order_by(SessionRecord.created_at.desc())
               .all())
    history = (SessionRecord.query
               .filter(SessionRecord.student_id == current_user.id,
                       SessionRecord.status != "pending")
               .order_by(SessionRecord.created_at.desc())
               .all())
    return render_template("portal/student_sessions.html",
                           pending=pending, history=history)


@portal_bp.route("/sessions/<int:session_id>/approve", methods=["POST"])
@student_required
def approve_session(session_id):
    sr = SessionRecord.query.get_or_404(session_id)
    # A student may only act on their own pending sessions.
    if sr.student_id != current_user.id or sr.status != "pending":
        flash("That session is not awaiting your approval.", "danger")
        return redirect(url_for("portal.student_sessions"))

    rating_raw = (request.form.get("rating", "") or "").strip()
    feedback = (request.form.get("feedback", "") or "").strip()
    try:
        rating = int(rating_raw)
        if not 1 <= rating <= 5:
            raise ValueError
    except ValueError:
        flash("Please give a rating from 1 to 5 stars.", "danger")
        return redirect(url_for("portal.student_sessions"))

    sr.status = "approved"
    sr.approved_at = datetime.utcnow()
    sr.rating = rating
    sr.feedback = feedback or None
    db.session.commit()
    flash("Session approved. Your progress has been updated.", "success")
    return redirect(url_for("portal.student_sessions"))


@portal_bp.route("/sessions/<int:session_id>/reject", methods=["POST"])
@student_required
def reject_session(session_id):
    sr = SessionRecord.query.get_or_404(session_id)
    if sr.student_id != current_user.id or sr.status != "pending":
        flash("That session is not awaiting your approval.", "danger")
        return redirect(url_for("portal.student_sessions"))
    sr.status = "rejected"
    db.session.commit()
    flash("Session marked as not attended.", "info")
    return redirect(url_for("portal.student_sessions"))
