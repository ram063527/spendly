from database.queries import get_category_breakdown


def test_get_category_breakdown_with_expenses(seeded_user):
    cats = get_category_breakdown(seeded_user)
    assert len(cats) == 7
    assert cats[0]["name"] == "Bills"  # largest single category
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    pcts = [c["pct"] for c in cats]
    assert all(isinstance(p, int) for p in pcts)
    assert sum(pcts) == 100


def test_get_category_breakdown_empty(empty_user):
    assert get_category_breakdown(empty_user) == []


def test_pct_rounding_remainder_goes_to_largest(temp_db):
    """Amounts chosen so naive rounding would sum to 99 or 101; the
    remainder must land on the largest category, not just any category."""
    from werkzeug.security import generate_password_hash

    conn = temp_db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Rounding User", "rounding@spendly.com", generate_password_hash("pw12345")),
        )
        user_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 10.00, "Food", "2026-08-01", "a"),
                (user_id, 10.00, "Transport", "2026-08-01", "b"),
                (user_id, 10.00, "Bills", "2026-08-01", "c"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    cats = get_category_breakdown(user_id)
    assert sum(c["pct"] for c in cats) == 100
    assert cats[0]["pct"] >= cats[1]["pct"] >= cats[2]["pct"]
