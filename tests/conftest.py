import pytest


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """Point database.db.DB_PATH at a throwaway sqlite file and create the
    schema there. Tests seed their own rows via the seeded_user/empty_user
    fixtures below."""
    from database import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    return db_module


@pytest.fixture
def seeded_user(temp_db):
    """One user with the 8 canonical seed expenses. Returns user_id."""
    from werkzeug.security import generate_password_hash

    conn = temp_db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 54.32, "Food", "2026-08-02", "Weekly groceries"),
                (user_id, 38.75, "Transport", "2026-08-04", "Gas fill-up"),
                (user_id, 112.40, "Bills", "2026-08-05", "Electricity bill"),
                (user_id, 22.15, "Health", "2026-08-08", "Pharmacy purchase"),
                (user_id, 28.00, "Entertainment", "2026-08-11", "Movie tickets"),
                (user_id, 65.99, "Shopping", "2026-08-14", "New running shoes"),
                (user_id, 47.60, "Food", "2026-08-17", "Dinner at restaurant"),
                (user_id, 15.00, "Other", "2026-08-20", "Miscellaneous purchase"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return user_id


@pytest.fixture
def empty_user(temp_db):
    """One user with zero expenses. Returns user_id."""
    from werkzeug.security import generate_password_hash

    conn = temp_db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty User", "empty@spendly.com", generate_password_hash("pw12345")),
        )
        user_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return user_id
