"""Seed the admin User Management portal with the 2028 student roster.

Source of truth: "2028Students" spreadsheet. These are DISPLAY-ONLY roster
rows — created with status='disabled' and no app access, so they appear in
/admin/users with their College/Major/Grad-Year/Sessions/Done?/Offers but
cannot log in or reach /macro or /competitions.

Idempotent:
  * matched by username (slug of the student's name)
  * new students are created
  * existing rows only have EMPTY profile fields filled (manual admin edits
    are preserved), except FORCE_FIELDS students whose profile is force-synced
    from the spreadsheet to correct stale data.
  * last_login is randomised within the last 3 days, set once on creation.
"""
import os
import random
import re
import secrets
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from migrations._dbapp import create_db_app
from models.database import db
from models.user import User

# (name, college, major, graduation_year, sessions, offers)
ROSTER = [
    ("Amber Feng", "Pomona", "Math & Stats & PPE", 2028, "28/50", "BofA S&T + Nomura + McKinsey"),
    ("Marcus Lo", "HKU", "Business Analytics", 2028, "15/15", "HK Barclays"),
    ("Gina Fu", "Cornell", "Stats & Econ", 2028, "16/50", "GS S&T"),
    ("Amber Sun", "Yale", "Econ & Math", 2028, "50/50", "GS S&T"),
    ("Caleb Hsu", "UCSB", "Data Science", 2028, "24/35", "HK Barclays"),
    ("Catherine Qin", "NYU Stern", "Finance", 2028, "12/15", None),
    ("Olivia Huang", "ASU", "Data Science", 2028, "16/35", None),
    ("Tyler Zhou", "Villanova U", "Econ", 2028, "14/15", None),
    ("Erin Bai", "Warwick", "Math", 2028, "28/35", None),
    ("Hazel Liu", "Barnard", "Gender Studies", 2028, "48/50", "GS IBD C&R"),
    ("Daniel Park", "NYU Stern", "Finance", 2028, "15/15", None),
    ("Derek Yu", "Villanova U", "History, Philosophy & Econ", 2028, "11/15", None),
    ("Rachel Yang", "Brown", "Math", 2028, "34/35", "Greenhill"),
    ("Andrew Liu", "Dartmouth", "Math", 2028, "25/35", None),
    ("Annie Meng", "Northwestern", "Econ & Data science", 2028, "16/50", "GS IBD C&R"),
    ("Hannah Shi", "IC", "Econ", 2028, "33/35", "Greenhill"),
    ("Felix Dong", "UCSB", "Data Science", 2028, "15/15", None),
    ("Stephanie He", "Cambridge", "Math", 2028, "11/15", "ING"),
    ("Eric Sun", "CMU", "Econ", 2028, "35/35", "BMO NYC"),
    ("Grace Lin", "Oxford", "Math", 2028, "11/15", "TD"),
    ("Sea Phongsphetrarat", "Cornell", "Hotel Administration", 2028, "50/50", "JPM IBD"),
    ("Kevin Zhao", "Manchester University", "Business Analytics", 2028, "24/35", "HSBC"),
    ("Ryan Cao", "ASU", "Math", 2028, "11/15", None),
    ("Brian Hong", "Manchester University", "Business Analytics", 2028, "12/15", None),
    ("James Li", "Duke", "Econ & Stats", 2028, "33/50", "Barclays NYC"),
    ("Alyssa Pan", "Cornell", "Math", 2028, "14/15", None),
    ("Megan Zhu", "NYU Stern", "Finance", 2028, "14/15", "ING"),
    ("Vivian Tang", "IC", "Math", 2028, "30/35", "Barclays London"),
    ("Aaron Gao", "UCL", "Data Science", 2028, "24/35", "TD"),
    ("Jessica Wei", "NYU Stern", "Finance", 2028, "11/15", None),
    ("Angela Jiang", "UCLA", "Data Theory", 2028, "40/50", "JPM IBD"),
    ("Brandon Kim", "Villanova U", "Data Science", 2028, "11/15", None),
    ("Ray Chu", "CMU", "Stats & ML", 2028, "28/50", "MS Investment Management"),
    ("Mariko Mita", "Cornell", "Hotel Administration", 2028, "37/50", "GS S&T"),
    ("Justin Lee", "UCSB", "Econ", 2028, "16/35", "HK GS WM"),
    ("Jenna Song", "Villanova U", "Math", 2028, "29/35", None),
    ("Chelsea Hu", "Barnard", "Econ & Math", 2028, "26/50", "GS IBD C&R"),
    ("Michael Xu", "NYU", "Data Science", 2028, "14/15", None),
    ("Nicole Deng", "Babson", "Business Analytics", 2028, "33/35", "Nomura NYC"),
    ("Jason Ma", "MIT Master", "Math", 2028, "17/35", "BMO NYC"),
    ("David Luo", "UCSD", "Econ", 2028, "13/35", None),
    ("Ethan Wang", "IC", "Business Analytics", 2028, "14/15", "TD"),
    ("Angela Zhang", "Umich", "Econ & Fin Math", 2028, "43/50", "Citi Macro Strategy"),
    ("Emily Tan", "NYU", "Math", 2028, "11/15", None),
    ("Sophia Chen", "Warwick", "Data Science", 2028, "27/35", "Citi"),
    ("Cindy Guo", "Cornell", "Econ", 2028, "28/35", None),
    ("Lily Wu", "Cambridge", "Business Analytics", 2028, "13/35", "UK SocGen"),
    ("Leon Wang", "UChicago", "Econ & Math", 2024, "50/50", "GS ER -> Citadel L/S"),
    ("Yifei Zhang", "Yale", "Math", 2028, "48/50", "Quant Edge"),
    ("Eric Shen", "UNSW", "Advanced Math", 2029, "8/50", None),
]

# Usernames whose profile fields should be force-synced from this spreadsheet
# even when already populated in prod — these rows carried stale data (wrong
# school or a superseded offer) that the current roster corrects.
FORCE_FIELDS = {"aaron.gao", "vivian.tang", "ray.chu", "angela.zhang", "leon.wang"}

EMAIL_DOMAIN = "students.newwhaletech.com"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", ".", name.strip().lower()).strip(".")
    return s or "student"


def _random_recent_login(now: datetime) -> datetime:
    return now - timedelta(seconds=random.randint(0, 3 * 24 * 3600))


def _gen_member_no(used: set) -> str:
    """A random 6-digit member number not already in `used`."""
    while True:
        candidate = f"{random.randint(100000, 999999)}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def seed():
    app = create_db_app()
    created, updated = 0, 0
    with app.app_context():
        now = datetime.utcnow()
        used_nos = {
            u.member_no
            for u in User.query.filter(User.member_no.isnot(None)).all()
            if u.member_no
        }
        for name, college, major, grad, sessions, offers in ROSTER:
            username = _slug(name)
            is_done = bool(offers)
            offers_val = offers or None
            user = User.query.filter(db.func.lower(User.username) == username).first()

            if user is None:
                user = User(
                    username=username,
                    email=f"{username}@{EMAIL_DOMAIN}",
                    full_name=name,
                    member_no=_gen_member_no(used_nos),
                    is_admin=False,
                    status="disabled",          # display-only roster, no login
                    email_verified=True,
                    email_verified_at=now,
                    allowed_apps="",            # no app access
                    college=college,
                    major=major,
                    graduation_year=grad,
                    sessions=sessions,
                    is_done=is_done,
                    offers=offers_val,
                    last_login=_random_recent_login(now),
                )
                user.set_password(secrets.token_urlsafe(24))
                db.session.add(user)
                created += 1
            else:
                force = username in FORCE_FIELDS
                # Fill-empty by default (manual admin edits preserved); FORCE_FIELDS
                # students overwrite even populated fields to correct stale data.
                if college and (force or not user.college):
                    user.college = college
                if major and (force or not user.major):
                    user.major = major
                if grad and (force or not user.graduation_year):
                    user.graduation_year = grad
                if sessions and (force or not user.sessions):
                    user.sessions = sessions
                if offers_val and (force or not user.offers):
                    user.offers = offers_val
                    user.is_done = is_done
                if not user.full_name:
                    user.full_name = name
                if not user.member_no:
                    user.member_no = _gen_member_no(used_nos)
                updated += 1

        db.session.commit()
        print(f"OK: Roster seed complete: {created} created, {updated} updated.")


def backfill_member_numbers():
    """Assign a random 6-digit member_no to any remaining user (e.g. admins)."""
    app = create_db_app()
    with app.app_context():
        used_nos = {
            u.member_no
            for u in User.query.filter(User.member_no.isnot(None)).all()
            if u.member_no
        }
        count = 0
        rows = User.query.filter(
            (User.member_no.is_(None)) | (User.member_no == "")
        ).all()
        for u in rows:
            u.member_no = _gen_member_no(used_nos)
            count += 1
        db.session.commit()
        print(f"OK: Backfilled member_no for {count} users.")


if __name__ == "__main__":
    seed()
