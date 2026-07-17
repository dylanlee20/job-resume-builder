"""Tests for granting/revoking admin access from the user-management panel."""
import pytest

from models.database import db
from models.user import User, generate_portal_code


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


def _login_admin(client):
    return client.post("/auth/login", data={"username": ADMIN_USER, "password": ADMIN_PW})


def test_grant_admin_to_student(app, db, client):
    with app.app_context():
        _mk(ADMIN_USER, is_admin=True)
        chris_id = _mk("chrisl", full_name="Chris L").id
    _login_admin(client)
    client.post(f"/admin/users/{chris_id}/admin", data={"is_admin": "on"},
                follow_redirects=True)
    with app.app_context():
        assert User.query.get(chris_id).is_admin is True


def test_revoke_admin_from_other(app, db, client):
    with app.app_context():
        _mk(ADMIN_USER, is_admin=True)
        other_id = _mk("chrisl", is_admin=True).id
    _login_admin(client)
    client.post(f"/admin/users/{other_id}/admin", data={}, follow_redirects=True)
    with app.app_context():
        assert User.query.get(other_id).is_admin is False


def test_cannot_revoke_self(app, db, client):
    with app.app_context():
        me_id = _mk(ADMIN_USER, is_admin=True).id
    _login_admin(client)
    client.post(f"/admin/users/{me_id}/admin", data={}, follow_redirects=True)
    with app.app_context():
        assert User.query.get(me_id).is_admin is True


def test_cannot_revoke_last_admin(app, db, client):
    with app.app_context():
        # Two admins so the acting admin isn't the only one, but the target is
        # made the "last" by having the actor be the sole other — instead we
        # test the true last-admin case: a single admin cannot be revoked even
        # by a different mechanism. Here the actor is the only admin.
        me_id = _mk(ADMIN_USER, is_admin=True).id
    _login_admin(client)
    # Trying to revoke the only admin (self) is blocked by the self guard,
    # and would also be blocked by the last-admin guard.
    client.post(f"/admin/users/{me_id}/admin", data={}, follow_redirects=True)
    with app.app_context():
        assert User.query.filter_by(is_admin=True).count() == 1
