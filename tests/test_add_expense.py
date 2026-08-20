import uuid

from app import app as flask_app
from database.queries import insert_expense


def _client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _register_and_login(client):
    email = f"add-expense-{uuid.uuid4().hex[:8]}@spendly.com"
    client.post(
        "/register",
        data={
            "name": "Add Expense Tester",
            "email": email,
            "password": "pw12345",
            "confirm_password": "pw12345",
        },
    )
    client.post("/login", data={"email": email, "password": "pw12345"})
    return email


# ------------------------------------------------------------------ #
# Unit tests — insert_expense                                         #
# ------------------------------------------------------------------ #

def test_insert_expense_creates_row(temp_db, empty_user):
    insert_expense(empty_user, 50.0, "Food", "2026-03-20", "Lunch")

    conn = temp_db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (empty_user,)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"
    assert row["description"] == "Lunch"


def test_insert_expense_with_none_description_stores_null(temp_db, empty_user):
    insert_expense(empty_user, 25.5, "Transport", "2026-03-21", None)

    conn = temp_db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (empty_user,)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["description"] is None


# ------------------------------------------------------------------ #
# Route tests                                                          #
# ------------------------------------------------------------------ #

def test_get_add_expense_redirects_when_unauthenticated():
    client = _client()
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_add_expense_redirects_when_unauthenticated():
    client = _client()
    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Food", "date": "2026-03-20", "description": ""},
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_add_expense_authenticated_renders_form():
    client = _client()
    _register_and_login(client)

    resp = client.get("/expenses/add")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<form" in body
    assert 'method="POST"' in body
    for category in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert category in body


def test_post_add_expense_valid_data_redirects_and_inserts():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "50.0", "category": "Food", "date": "2026-03-20", "description": "Lunch"},
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    profile_resp = client.get("/profile")
    body = profile_resp.get_data(as_text=True)
    assert "Lunch" in body
    assert "50.00" in body


def test_post_add_expense_missing_amount():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "", "category": "Food", "date": "2026-03-20", "description": ""},
    )
    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)


def test_post_add_expense_non_finite_amount():
    client = _client()
    _register_and_login(client)

    for bad_amount in ["inf", "-inf", "nan"]:
        resp = client.post(
            "/expenses/add",
            data={"amount": bad_amount, "category": "Food", "date": "2026-03-20", "description": ""},
        )
        assert resp.status_code == 200
        assert "auth-error" in resp.get_data(as_text=True)


def test_post_add_expense_zero_amount():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "0", "category": "Food", "date": "2026-03-20", "description": ""},
    )
    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)


def test_post_add_expense_non_numeric_amount():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "abc", "category": "Food", "date": "2026-03-20", "description": ""},
    )
    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)


def test_post_add_expense_invalid_category():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Groceries", "date": "2026-03-20", "description": ""},
    )
    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)


def test_post_add_expense_invalid_date():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Food", "date": "not-a-date", "description": ""},
    )
    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)


def test_post_add_expense_no_description_is_optional():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Food", "date": "2026-03-20"},
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    profile_resp = client.get("/profile")
    assert profile_resp.status_code == 200


def test_post_add_expense_error_retains_previous_values():
    client = _client()
    _register_and_login(client)

    resp = client.post(
        "/expenses/add",
        data={"amount": "42.5", "category": "NotACategory", "date": "2026-03-20", "description": "Keep me"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'value="42.5"' in body
    assert 'value="Keep me"' in body
