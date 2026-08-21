"""Tests for the Edit Expense feature (Step 8).

Covers the two new query helpers in database/queries.py
(get_expense_by_id, update_expense) and the GET/POST
/expenses/<id>/edit route, per .claude/specs/08-edit-expense.md.

Unit tests use the temp_db/seeded_user/empty_user fixtures from
conftest.py (isolated sqlite file per test). Route tests use the
_client()/_register_and_login() pattern from test_add_expense.py,
which exercises the app against its real configured database.
"""

import re
import uuid

import pytest

from app import app as flask_app
from database.db import get_user_by_email
from database.queries import get_expense_by_id, insert_expense, update_expense

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def _client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _register_and_login(client):
    email = f"edit-expense-{uuid.uuid4().hex[:8]}@spendly.com"
    client.post(
        "/register",
        data={
            "name": "Edit Expense Tester",
            "email": email,
            "password": "pw12345",
            "confirm_password": "pw12345",
        },
    )
    client.post("/login", data={"email": email, "password": "pw12345"})
    return email


def _user_id_for(email):
    return get_user_by_email(email)["id"]


def _category_is_preselected(body, category):
    """True if `category`'s <option> carries the `selected` attribute,
    tolerant of attribute ordering."""
    escaped = re.escape(category)
    patterns = [
        rf'<option[^>]*value="{escaped}"[^>]*selected',
        rf'<option[^>]*selected[^>]*value="{escaped}"',
    ]
    return any(re.search(p, body, re.IGNORECASE) for p in patterns)


def _seeded_expense_row(temp_db, user_id):
    """Fetches the single expense row owned by user_id via a raw,
    parameterised query against the isolated temp_db."""
    conn = temp_db.get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses WHERE user_id = ? "
            "ORDER BY id ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Unit tests — get_expense_by_id                                      #
# ------------------------------------------------------------------ #

def test_get_expense_by_id_valid_id_correct_user_returns_row(temp_db, seeded_user):
    original = _seeded_expense_row(temp_db, seeded_user)

    row = get_expense_by_id(original["id"], seeded_user)

    assert row is not None, "Expected a matching row for the owning user"
    assert row["id"] == original["id"]
    assert row["amount"] == original["amount"]
    assert row["category"] == original["category"]
    assert row["date"] == original["date"]
    assert row["description"] == original["description"]


def test_get_expense_by_id_valid_id_wrong_user_returns_none(temp_db, seeded_user, empty_user):
    original = _seeded_expense_row(temp_db, seeded_user)

    row = get_expense_by_id(original["id"], empty_user)

    assert row is None, "Expense belonging to another user must not be returned"


def test_get_expense_by_id_nonexistent_id_returns_none(temp_db, seeded_user):
    row = get_expense_by_id(999999999, seeded_user)

    assert row is None, "A non-existent expense id must return None"


# ------------------------------------------------------------------ #
# Unit tests — update_expense                                         #
# ------------------------------------------------------------------ #

def test_update_expense_correct_user_updates_row(temp_db, seeded_user):
    original = _seeded_expense_row(temp_db, seeded_user)

    update_expense(
        original["id"],
        seeded_user,
        99.0,
        original["category"],
        original["date"],
        original["description"],
    )

    conn = temp_db.get_db()
    try:
        row = conn.execute(
            "SELECT amount FROM expenses WHERE id = ?", (original["id"],)
        ).fetchone()
    finally:
        conn.close()

    assert row["amount"] == 99.0, "Row in DB must reflect the updated amount"


def test_update_expense_wrong_user_leaves_row_unchanged(temp_db, seeded_user, empty_user):
    original = _seeded_expense_row(temp_db, seeded_user)

    update_expense(
        original["id"],
        empty_user,
        555.0,
        original["category"],
        original["date"],
        original["description"],
    )

    conn = temp_db.get_db()
    try:
        row = conn.execute(
            "SELECT amount FROM expenses WHERE id = ?", (original["id"],)
        ).fetchone()
    finally:
        conn.close()

    assert row["amount"] == original["amount"], (
        "Update scoped to the wrong user_id must affect 0 rows and leave "
        "the original value intact"
    )


# ------------------------------------------------------------------ #
# Route tests — GET /expenses/<id>/edit                                #
# ------------------------------------------------------------------ #

def test_get_edit_expense_redirects_when_unauthenticated():
    client = _client()
    resp = client.get("/expenses/1/edit")

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_edit_expense_authenticated_own_expense_renders_prefilled_form():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)

    expense_id = insert_expense(user_id, 75.5, "Health", "2026-05-10", "Dentist visit")

    resp = client.get(f"/expenses/{expense_id}/edit")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<form" in body
    assert 'value="75.5"' in body, "Amount must be pre-filled with the current value"
    assert 'value="2026-05-10"' in body, "Date must be pre-filled with the current value"
    assert 'value="Dentist visit"' in body, "Description must be pre-filled with the current value"
    assert _category_is_preselected(body, "Health"), "Category <select> must pre-select the current category"


def test_get_edit_expense_authenticated_other_users_expense_returns_404():
    owner_client = _client()
    owner_email = _register_and_login(owner_client)
    owner_id = _user_id_for(owner_email)
    expense_id = insert_expense(owner_id, 40.0, "Food", "2026-04-01", "Owner's lunch")

    other_client = _client()
    _register_and_login(other_client)

    resp = other_client.get(f"/expenses/{expense_id}/edit")

    assert resp.status_code == 404, "Editing another user's expense must 404"


def test_get_edit_expense_authenticated_nonexistent_id_returns_404():
    client = _client()
    _register_and_login(client)

    resp = client.get("/expenses/999999999/edit")

    assert resp.status_code == 404, "A non-existent expense id must 404"


# ------------------------------------------------------------------ #
# Route tests — POST /expenses/<id>/edit                               #
# ------------------------------------------------------------------ #

def test_post_edit_expense_redirects_when_unauthenticated():
    client = _client()
    resp = client.post(
        "/expenses/1/edit",
        data={"amount": "10", "category": "Food", "date": "2026-03-20", "description": ""},
    )

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_edit_expense_valid_data_redirects_and_updates_db():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "88.25", "category": "Shopping", "date": "2026-06-15", "description": "Updated item"},
    )

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    row = get_expense_by_id(expense_id, user_id)
    assert row is not None
    assert row["amount"] == 88.25
    assert row["category"] == "Shopping"
    assert row["date"] == "2026-06-15"
    assert row["description"] == "Updated item"


def test_post_edit_expense_other_users_expense_returns_404_and_db_unchanged():
    owner_client = _client()
    owner_email = _register_and_login(owner_client)
    owner_id = _user_id_for(owner_email)
    expense_id = insert_expense(owner_id, 40.0, "Food", "2026-04-01", "Owner's lunch")

    other_client = _client()
    _register_and_login(other_client)

    resp = other_client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "999", "category": "Shopping", "date": "2026-06-15", "description": "Hijacked"},
    )

    assert resp.status_code == 404, "Editing another user's expense must 404"

    row = get_expense_by_id(expense_id, owner_id)
    assert row["amount"] == 40.0, "The owner's expense must be untouched by another user's attempt"
    assert row["description"] == "Owner's lunch"


def test_post_edit_expense_missing_amount():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "", "category": "Food", "date": "2026-01-01", "description": ""},
    )

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    row = get_expense_by_id(expense_id, user_id)
    assert row["amount"] == 20.0, "Invalid submission must not modify the stored row"


def test_post_edit_expense_zero_amount():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "0", "category": "Food", "date": "2026-01-01", "description": ""},
    )

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    row = get_expense_by_id(expense_id, user_id)
    assert row["amount"] == 20.0, "Invalid submission must not modify the stored row"


def test_post_edit_expense_non_numeric_amount():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "abc", "category": "Food", "date": "2026-01-01", "description": ""},
    )

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    row = get_expense_by_id(expense_id, user_id)
    assert row["amount"] == 20.0, "Invalid submission must not modify the stored row"


def test_post_edit_expense_invalid_category():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "20", "category": "Groceries", "date": "2026-01-01", "description": ""},
    )

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    row = get_expense_by_id(expense_id, user_id)
    assert row["category"] == "Food", "Invalid submission must not modify the stored row"


def test_post_edit_expense_invalid_date():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "20", "category": "Food", "date": "not-a-date", "description": ""},
    )

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    row = get_expense_by_id(expense_id, user_id)
    assert row["date"] == "2026-01-01", "Invalid submission must not modify the stored row"


def test_post_edit_expense_no_description_saves_null():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "20", "category": "Food", "date": "2026-01-01"},
    )

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    row = get_expense_by_id(expense_id, user_id)
    assert row["description"] is None, "Omitting description must store NULL, not raise an error"


def test_post_edit_expense_validation_error_retains_submitted_values():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "42.5", "category": "NotACategory", "date": "2026-02-02", "description": "Keep me"},
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'value="42.5"' in body, "The re-rendered form must retain the submitted amount, not the original"
    assert 'value="Keep me"' in body, "The re-rendered form must retain the submitted description, not the original"


# ------------------------------------------------------------------ #
# Route tests — profile.html Edit link                                 #
# ------------------------------------------------------------------ #

def test_profile_page_lists_edit_link_for_each_transaction():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 33.0, "Bills", "2026-07-01", "Water bill")

    resp = client.get("/profile")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f"/expenses/{expense_id}/edit" in body, "Each transaction row must link to its own edit URL"
