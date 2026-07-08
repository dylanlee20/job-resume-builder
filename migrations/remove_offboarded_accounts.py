"""Remove offboarded / duplicate roster accounts.

Idempotent one-off cleanup:
  * siyuan111 (member #189865) — offboarded, deleted outright.
  * mia7 (member #534837) — an empty duplicate (0/50, no offer) folded into
    the canonical "Amber Feng" roster row, so the standalone account is removed.

Also removes any leftover display-only rows the seed used to create for these
two (usernames 'mia' / 'siyuan') so they don't linger after being dropped from
the roster. Only ever touches non-admin accounts, matched by exact member
number or exact username, so re-runs are safe no-ops.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from migrations._dbapp import create_db_app
from models.database import db
from models.session_record import SessionRecord
from models.user import User

# Exact member numbers pulled from the live admin roster.
MEMBER_NOS = {"189865", "534837"}
# Legacy seed slugs for the same two people (Mia -> Amber Feng, Siyuan removed).
USERNAMES = {"mia", "siyuan", "mia7", "siyuan111"}


def migrate():
    app = create_db_app()
    with app.app_context():
        targets = (
            User.query.filter(
                db.or_(
                    User.member_no.in_(MEMBER_NOS),
                    db.func.lower(User.username).in_(USERNAMES),
                )
            )
            .filter(User.is_admin.is_(False))
            .all()
        )
        if not targets:
            print("OK: no offboarded accounts to remove.")
            return

        removed = []
        for user in targets:
            # student_id is a nullable FK with no cascade — unlink any sessions
            # first so the delete can't orphan or fail on a FK constraint.
            SessionRecord.query.filter_by(student_id=user.id).update(
                {"student_id": None}, synchronize_session=False
            )
            removed.append(f"{user.username} (#{user.member_no})")
            db.session.delete(user)

        db.session.commit()
        print(f"OK: removed {len(removed)} offboarded account(s): {', '.join(removed)}")


if __name__ == "__main__":
    migrate()
