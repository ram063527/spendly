import uuid

from app import app as flask_app


def _client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_profile_redirects_when_unauthenticated():
    client = _client()
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_for_seeded_demo_user():
    client = _client()
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    # NOTE: the spec's Definition-of-done cites ₹346.24 for the seed user,
    # but the actual seed data in database/db.py sums to 384.21 (verified
    # by hand: 54.32+38.75+112.40+22.15+28.00+65.99+47.60+15.00). The
    # correct SUM over real data is asserted here; the spec's figure is stale.
    assert "384.21" in body
    assert "Bills" in body
    for category in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert category in body


def test_profile_for_brand_new_user_has_empty_state():
    # Registers a fresh, uniquely-emailed user rather than reusing/mutating
    # the demo user — seed_db() only seeds once, so any accidental change
    # to the demo user's expenses would permanently affect the test above.
    client = _client()
    email = f"new-{uuid.uuid4().hex[:8]}@spendly.com"
    client.post(
        "/register",
        data={
            "name": "New User",
            "email": email,
            "password": "pw12345",
            "confirm_password": "pw12345",
        },
    )
    client.post("/login", data={"email": email, "password": "pw12345"})
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹0.00" in body
