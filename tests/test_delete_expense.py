"""Tests for the Delete Expense feature (Step 9).

Covers the new remove_expense query helper in database/queries.py and the
POST /expenses/<id>/delete route, per .claude/specs/09-delete-expense.md.

Unit tests use the temp_db/seeded_user/empty_user fixtures from
conftest.py (isolated sqlite file per test). Route tests use the
_client()/_register_and_login() pattern from test_edit_expense.py,
which exercises the app against its real configured database.
"""

import uuid

from app import app as flask_app
from database.db import get_user_by_email
from database.queries import get_expense_by_id, insert_expense, remove_expense


def _client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _register_and_login(client):
    email = f"delete-expense-{uuid.uuid4().hex[:8]}@spendly.com"
    client.post(
        "/register",
        data={
            "name": "Delete Expense Tester",
            "email": email,
            "password": "pw12345",
            "confirm_password": "pw12345",
        },
    )
    client.post("/login", data={"email": email, "password": "pw12345"})
    return email


def _user_id_for(email):
    return get_user_by_email(email)["id"]


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


def _row_exists(temp_db, expense_id):
    conn = temp_db.get_db()
    try:
        row = conn.execute("SELECT id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    finally:
        conn.close()
    return row is not None


# ------------------------------------------------------------------ #
# Unit tests — remove_expense                                         #
# ------------------------------------------------------------------ #

def test_remove_expense_correct_user_removes_row(temp_db, seeded_user):
    original = _seeded_expense_row(temp_db, seeded_user)

    remove_expense(original["id"], seeded_user)

    assert not _row_exists(temp_db, original["id"]), "Row must be removed from the DB"


def test_remove_expense_wrong_user_leaves_row_untouched(temp_db, seeded_user, empty_user):
    original = _seeded_expense_row(temp_db, seeded_user)

    remove_expense(original["id"], empty_user)

    assert _row_exists(temp_db, original["id"]), (
        "Delete scoped to the wrong user_id must affect 0 rows and leave the row intact"
    )


def test_remove_expense_nonexistent_id_raises_no_error(temp_db, empty_user):
    remove_expense(999999999, empty_user)
    # No exception raised — the DELETE simply affects 0 rows.


# ------------------------------------------------------------------ #
# Route tests — POST /expenses/<id>/delete                            #
# ------------------------------------------------------------------ #

def test_post_delete_expense_redirects_when_unauthenticated():
    client = _client()
    resp = client.post("/expenses/1/delete")

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_delete_expense_own_expense_redirects_and_removes_row():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.post(f"/expenses/{expense_id}/delete")

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]
    assert get_expense_by_id(expense_id, user_id) is None, "Expense must no longer exist in the DB"


def test_post_delete_expense_other_users_expense_returns_404_and_db_unchanged():
    owner_client = _client()
    owner_email = _register_and_login(owner_client)
    owner_id = _user_id_for(owner_email)
    expense_id = insert_expense(owner_id, 40.0, "Food", "2026-04-01", "Owner's lunch")

    other_client = _client()
    _register_and_login(other_client)

    resp = other_client.post(f"/expenses/{expense_id}/delete")

    assert resp.status_code == 404, "Deleting another user's expense must 404"
    row = get_expense_by_id(expense_id, owner_id)
    assert row is not None, "The owner's expense must be untouched by another user's attempt"


def test_post_delete_expense_nonexistent_id_returns_404():
    client = _client()
    _register_and_login(client)

    resp = client.post("/expenses/999999999/delete")

    assert resp.status_code == 404, "A non-existent expense id must 404"


def test_get_delete_expense_returns_405():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 20.0, "Food", "2026-01-01", "Original")

    resp = client.get(f"/expenses/{expense_id}/delete")

    assert resp.status_code == 405, "GET on the delete route must not be allowed"


def test_get_delete_expense_returns_405_when_unauthenticated():
    client = _client()

    resp = client.get("/expenses/1/delete")

    assert resp.status_code == 405, "Method restriction applies before the auth check"


# ------------------------------------------------------------------ #
# Route tests — profile.html Delete button                            #
# ------------------------------------------------------------------ #

def test_profile_page_lists_delete_form_for_each_transaction():
    client = _client()
    email = _register_and_login(client)
    user_id = _user_id_for(email)
    expense_id = insert_expense(user_id, 33.0, "Bills", "2026-07-01", "Water bill")

    resp = client.get("/profile")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f"/expenses/{expense_id}/delete" in body, "Each transaction row must have a delete form for its own id"
