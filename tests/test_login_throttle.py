"""Login brute-force throttling tests.

Failed logins are rate-limited per IP and per username (8 failures / 15 min).
A successful login clears the counters so ordinary users are never blocked.
"""
from utils.rate_limiter import login_limiter


def _attempt(client, username, password):
    return client.post(
        '/auth/login',
        data={'username': username, 'password': password},
        follow_redirects=False,
    )


def test_wrong_password_returns_200_until_limit(client, verified_user):
    # Up to the limit (8), each bad attempt just re-renders the login form.
    for _ in range(login_limiter._max):
        resp = _attempt(client, 'verifieduser', 'wrong-password')
        assert resp.status_code == 200


def test_blocked_after_too_many_failures(client, verified_user):
    for _ in range(login_limiter._max):
        _attempt(client, 'verifieduser', 'wrong-password')

    # The next attempt is throttled regardless of what is typed.
    resp = _attempt(client, 'verifieduser', 'wrong-password')
    assert resp.status_code == 429
    assert b'Too many failed login attempts' in resp.data


def test_correct_password_also_blocked_while_throttled(client, verified_user):
    # Even the *right* password is refused once the limit is hit — the guard
    # runs before the password is checked, so an attacker can't sneak past.
    for _ in range(login_limiter._max):
        _attempt(client, 'verifieduser', 'wrong-password')

    resp = _attempt(client, 'verifieduser', 'password123')
    assert resp.status_code == 429


def test_successful_login_resets_counter(client, verified_user):
    # A few failed attempts, then a success, must clear the slate.
    for _ in range(login_limiter._max - 1):
        _attempt(client, 'verifieduser', 'wrong-password')

    good = _attempt(client, 'verifieduser', 'password123')
    assert good.status_code == 302  # redirected in, not re-rendered

    # Drop the session so we're anonymous again (a logged-in client would just
    # be redirected away from the login form).
    client.get('/auth/logout')

    # Counters cleared: a fresh run of failures is allowed again, no 429 yet.
    for _ in range(login_limiter._max):
        resp = _attempt(client, 'verifieduser', 'wrong-password')
        assert resp.status_code == 200


def test_block_is_per_ip_across_usernames(client, verified_user, sample_user):
    # Throttling is per source IP, not per username: an attacker spraying many
    # usernames from one client is still blocked after the IP budget is spent
    # (and this avoids the targeted account-lockout DoS of per-username keying).
    for i in range(login_limiter._max):
        _attempt(client, f'user{i}', 'wrong-password')

    resp = _attempt(client, 'verifieduser', 'wrong-password')
    assert resp.status_code == 429
