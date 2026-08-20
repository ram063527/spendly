"""Tests for the Analytics "Coming Soon" feature.

Spec (given directly by the task — no specs/ file exists for this feature):
- GET /analytics
- Unauthenticated requests (no session["user_id"]) redirect (302) to /login,
  matching the existing /profile route's auth-gating pattern.
- Authenticated requests (valid session["user_id"]) return 200 and render
  analytics.html, whose body contains "Advanced Analytics" and "Coming Soon".
- Read-only informational page: no POST method, no DB side effects.

These tests are written purely from that behavioral contract; app.py's
implementation was not consulted. Fixtures reuse tests/conftest.py's
temp_db/seeded_user/empty_user, and follow the local-`client`-fixture +
`_login` helper convention established in tests/test_profile_date_filter.py.
"""

import pytest

from app import app as flask_app

SEEDED_EMAIL = "demo@spendly.com"
SEEDED_PASSWORD = "demo123"
EMPTY_EMAIL = "empty@spendly.com"
EMPTY_PASSWORD = "pw12345"

ANALYTICS_HEADING = "Advanced Analytics"
ANALYTICS_SUBTEXT = "Coming Soon"


@pytest.fixture
def client(temp_db):
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_analytics_redirects_when_unauthenticated(client):
    resp = client.get("/analytics")
    assert resp.status_code == 302, "Expected a redirect for an unauthenticated /analytics request"
    assert "/login" in resp.headers["Location"], "Expected the redirect to point at /login"


def test_analytics_redirect_does_not_render_analytics_content(client):
    """The 302 response itself must not leak the analytics page body."""
    resp = client.get("/analytics")
    body = resp.get_data(as_text=True)
    assert ANALYTICS_HEADING not in body, "Redirect response must not contain analytics.html content"
    assert ANALYTICS_SUBTEXT not in body, "Redirect response must not contain analytics.html content"


def test_analytics_redirect_follows_to_login_page_not_analytics(client):
    resp = client.get("/analytics", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ANALYTICS_HEADING not in body, "Following the redirect should land on /login, not analytics content"
    assert ANALYTICS_SUBTEXT not in body


# ---------------------------------------------------------------------------
# Happy path — authenticated access
# ---------------------------------------------------------------------------


def test_analytics_authenticated_returns_200_with_expected_content(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/analytics")
    assert resp.status_code == 200, "Expected 200 OK for an authenticated /analytics request"
    body = resp.get_data(as_text=True)
    assert ANALYTICS_HEADING in body, "Expected 'Advanced Analytics' heading in the rendered page"
    assert ANALYTICS_SUBTEXT in body, "Expected 'Coming Soon' text in the rendered page"


def test_analytics_authenticated_empty_user_still_returns_200(client, empty_user):
    """The page is a static informational placeholder — it should not
    depend on the user having any expense data."""
    _login(client, EMPTY_EMAIL, EMPTY_PASSWORD)
    resp = client.get("/analytics")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ANALYTICS_HEADING in body
    assert ANALYTICS_SUBTEXT in body


# ---------------------------------------------------------------------------
# Read-only: no POST / other side effects
# ---------------------------------------------------------------------------


def test_analytics_post_not_allowed(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.post("/analytics")
    assert resp.status_code == 405, "Expected POST /analytics to be rejected as Method Not Allowed"


def test_analytics_post_unauthenticated_is_not_200(client):
    resp = client.post("/analytics")
    assert resp.status_code != 200
