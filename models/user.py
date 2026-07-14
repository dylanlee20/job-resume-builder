"""User model with authentication and email verification support."""
import random
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from models.database import db


class User(UserMixin, db.Model):
    """User account model."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # 'active' (login OK), 'frozen' (temporarily blocked), 'disabled' (revoked).
    status = db.Column(db.String(20), default='active', nullable=False, index=True)

    # Kept on the model for legacy DB schemas, but never enforced anymore —
    # email verification was disabled when the app moved to admin-issued accounts.
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    # Legacy columns kept NOT NULL in the SQLite schema from an earlier
    # premium-tier / per-user SMTP era. The features are retired but the
    # constraints remain, so the model must supply defaults on INSERT.
    tier = db.Column(db.String(20), default='free', nullable=False)
    smtp_use_tls = db.Column(db.Boolean, default=True, nullable=False)

    # Comma-separated list of app codes the user can reach. Empty = no
    # access to any gated app. Admins bypass this check entirely. See
    # nginx auth_request flow for how this is enforced on /macro and
    # /competitions; the main Flask app gates itself via before_request.
    allowed_apps = db.Column(db.String(100), default='', nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Student-roster profile fields (surfaced in the admin User Management page).
    college = db.Column(db.String(120), nullable=True)
    major = db.Column(db.String(200), nullable=True)
    graduation_year = db.Column(db.Integer, nullable=True)
    # Coaching-session progress, stored as the raw "done/total" string (e.g. "28/50").
    sessions = db.Column(db.String(40), nullable=True)
    # Whether the student is placed/finished; if so, `offers` lists the firms.
    is_done = db.Column(db.Boolean, default=False, nullable=False)
    offers = db.Column(db.String(255), nullable=True)
    # Real display name and a public-facing 6-digit member number shown in the
    # admin roster instead of the raw sequential DB id.
    full_name = db.Column(db.String(120), nullable=True)
    member_no = db.Column(db.String(6), nullable=True, index=True)

    # --- Roles, portal identity, and mentor curriculum access ---
    # is_admin (above) marks staff. is_mentor marks a coaching mentor.
    # Neither flag set => a student.
    is_mentor = db.Column(db.Boolean, default=False, nullable=False)
    # 5-digit public User ID shown top-right in the portal and used as the
    # "Student ID" mentors select on. Unique across ALL accounts.
    portal_code = db.Column(db.String(5), unique=True, nullable=True, index=True)
    # Comma-separated curriculum section slugs a MENTOR may view. Empty = none.
    # Ignored for students and admins, who always see every curriculum.
    allowed_curriculums = db.Column(db.String(160), default='', nullable=False)
    # Mentor payout currency (ISO 4217). Students pay in their own currency,
    # captured per-payment on StudentPayment.
    payout_currency = db.Column(db.String(3), default='USD', nullable=False)
    # Student package size — the denominator (y) in the Progress x/y bar.
    total_sessions = db.Column(db.Integer, nullable=True)
    # Student's exchange rate to USD captured at issuance (what they paid at).
    # Multiply their local-currency amount by this to get USD.
    exchange_rate = db.Column(db.Numeric(12, 6), nullable=True)

    def __repr__(self):
        return f'<User {self.username} status={self.status}>'

    @property
    def role(self) -> str:
        if self.is_admin:
            return 'admin'
        if self.is_mentor:
            return 'mentor'
        return 'student'

    # --- Session-progress / plan helpers (admin roster display) ---
    # The sessions denominator encodes the plan tier; blank defaults to Obsidian.
    _PLAN_BY_TOTAL = {50: 'Obsidian', 35: 'Platinum', 15: 'Gold'}

    def _session_parts(self):
        raw = (self.sessions or '').strip()
        if '/' in raw:
            done_s, total_s = raw.split('/', 1)
            try:
                return int(done_s), int(total_s)
            except ValueError:
                return None, None
        return None, None

    @property
    def sessions_total(self) -> int:
        # Explicit package size wins; fall back to the legacy "done/total"
        # string, then to Obsidian's 50.
        if self.total_sessions:
            return self.total_sessions
        _, total = self._session_parts()
        return total or 50

    @property
    def sessions_completed(self) -> int:
        """Count of the student's APPROVED sessions (drives the Progress bar).

        Memoized per instance so rendering the roster (where both
        progress_display and sessions_pct read it) issues one COUNT per user,
        not several.
        """
        cached = self.__dict__.get('_sessions_completed_cache')
        if cached is None:
            from models.session_record import SessionRecord
            cached = SessionRecord.query.filter_by(
                student_id=self.id, status='approved'
            ).count()
            self.__dict__['_sessions_completed_cache'] = cached
        return cached

    @property
    def sessions_pct(self) -> int:
        total = self.sessions_total
        if not total:
            return 0
        return max(0, min(100, round(100 * self.sessions_completed / total)))

    @property
    def progress_display(self) -> str:
        """The 'x/y' label: approved sessions over package total."""
        return f"{self.sessions_completed}/{self.sessions_total}"

    @property
    def plan(self) -> str:
        return self._PLAN_BY_TOTAL.get(self.sessions_total, 'Obsidian')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def mark_email_verified(self) -> None:
        self.email_verified = True
        self.email_verified_at = datetime.utcnow()

    def needs_email_verification(self) -> bool:
        # Email verification was retired in favor of admin-issued accounts.
        return False

    @property
    def is_active_account(self) -> bool:
        return (self.status or 'active') == 'active'

    @property
    def is_frozen(self) -> bool:
        return self.status == 'frozen'

    @property
    def is_disabled(self) -> bool:
        return self.status == 'disabled'

    APP_CODES = ('main', 'macro', 'competitions')

    @property
    def app_set(self) -> set:
        return {a.strip() for a in (self.allowed_apps or '').split(',') if a.strip()}

    def has_app(self, code: str) -> bool:
        if self.is_admin:
            return True
        if not self.is_active_account:
            return False
        return code in self.app_set

    def set_allowed_apps(self, codes) -> None:
        clean = sorted({c for c in codes if c in self.APP_CODES})
        self.allowed_apps = ','.join(clean)

    # Curriculum section slugs a mentor may view. Mirrors the allowed_apps
    # pattern above. Kept in sync with services.slides_service section slugs.
    CURRICULUM_CODES = (
        '01-behavioral-and-fit',
        '02-technical-generalist',
        '03-industry-specific',
        '04-sales-and-trading',
        '05-quant',
        '07-modeling-quant',
        '08-consulting',
    )

    @property
    def curriculum_set(self) -> set:
        return {c.strip() for c in (self.allowed_curriculums or '').split(',') if c.strip()}

    def has_curriculum(self, slug: str) -> bool:
        # Only mentors are gated; admins and students see every curriculum.
        if not self.is_mentor:
            return True
        if not self.is_active_account:
            return False
        return slug in self.curriculum_set

    def set_allowed_curriculums(self, codes) -> None:
        clean = sorted({c for c in codes if c in self.CURRICULUM_CODES})
        self.allowed_curriculums = ','.join(clean)

    @property
    def current_rate(self):
        """The mentor's hourly rate in force right now, or None."""
        from models.mentor_rate import MentorRate
        return MentorRate.effective_at(self.id, datetime.utcnow())

    def record_login(self) -> None:
        self.last_login = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'allowed_apps': sorted(self.app_set),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


def generate_portal_code() -> str:
    """Return a 5-digit portal/User ID not already used by any account.

    Uniqueness is enforced by the DB unique constraint; this retry loop just
    avoids the obvious collisions. Mirrors _gen_member_no in the roster seed.
    """
    for _ in range(50):
        code = str(random.randint(10000, 99999))
        if not User.query.filter_by(portal_code=code).first():
            return code
    # Extremely unlikely; fall back to a wider scan-free candidate.
    raise RuntimeError("Could not allocate a unique portal_code")


def create_admin_user(username: str, password: str, email: str) -> User:
    """Idempotently create the default admin user."""
    existing = User.query.filter_by(username=username).first()
    if existing:
        changed = False
        if not existing.email_verified:
            existing.email_verified = True
            existing.email_verified_at = datetime.utcnow()
            changed = True
        if not existing.portal_code:
            existing.portal_code = generate_portal_code()
            changed = True
        if changed:
            db.session.commit()
        return existing

    admin = User(
        username=username,
        email=email,
        is_admin=True,
        email_verified=True,
        email_verified_at=datetime.utcnow(),
        portal_code=generate_portal_code(),
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin
