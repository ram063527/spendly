"""Pure query helpers for the profile page. No Flask imports — callers
(routes) pass in a user_id and get back plain dicts/lists. Each function
opens its own connection via get_db() and closes it before returning,
matching the convention in database/db.py."""

from datetime import datetime

from database.db import get_db


def _date_filter_clause(date_from, date_to):
    """Returns (sql_fragment, params_tuple) for an optional inclusive date
    range. Both bounds must be provided for the filter to apply."""
    if date_from is not None and date_to is not None:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


def get_user_by_id(user_id):
    """Returns dict with name, email, member_since ("Month YYYY", derived
    from users.created_at), or None if no such user."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    return {"name": row["name"], "email": row["email"], "member_since": created.strftime("%B %Y")}


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Returns dict with total_spent, transaction_count, top_category.
    No expenses -> {"total_spent": 0, "transaction_count": 0, "top_category": "—"}."""
    clause, date_params = _date_filter_clause(date_from, date_to)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt FROM expenses "
            "WHERE user_id = ?" + clause,
            (user_id, *date_params),
        ).fetchone()
        if totals["cnt"] == 0:
            return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
        top = conn.execute(
            "SELECT category, SUM(amount) AS cat_total FROM expenses WHERE user_id = ?"
            + clause + " GROUP BY category ORDER BY cat_total DESC, category ASC LIMIT 1",
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()
    return {"total_spent": round(totals["total"], 2), "transaction_count": totals["cnt"], "top_category": top["category"]}


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Returns list of dicts (date, description, category, amount), newest
    first. No expenses -> []."""
    clause, date_params = _date_filter_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()
    transactions = []
    for row in rows:
        d = datetime.strptime(row["date"], "%Y-%m-%d")
        transactions.append({
            "id": row["id"],
            "date": f"{d.strftime('%b')} {d.day}, {d.year}",
            "description": row["description"],
            "category": row["category"],
            "amount": round(row["amount"], 2),
        })
    return transactions


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Returns list of dicts (name, amount, pct), ordered by amount desc.
    pct values are ints summing to 100 (largest category absorbs rounding
    remainder). No expenses -> []."""
    clause, date_params = _date_filter_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ?"
            + clause + " GROUP BY category ORDER BY total DESC, category ASC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    grand_total = sum(r["total"] for r in rows)
    pcts = [round(r["total"] / grand_total * 100) for r in rows]
    pcts[0] += 100 - sum(pcts)  # largest category absorbs the rounding remainder
    return [{"name": r["category"], "amount": round(r["total"], 2), "pct": p} for r, p in zip(rows, pcts)]


def insert_expense(user_id, amount, category, expense_date, description):
    """Inserts a new expense row and returns its new id."""
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, expense_date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id, user_id):
    """Returns a dict (id, amount, category, date, description) if the
    expense exists and belongs to user_id, else None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def update_expense(expense_id, user_id, amount, category, expense_date, description):
    """Updates an existing expense row, scoped to both id and user_id so a
    user can never modify another user's expense."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category, expense_date, description, expense_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def remove_expense(expense_id, user_id):
    """Deletes an expense row, scoped to both id and user_id so a user can
    never delete another user's expense. A non-existent id or mismatched
    user_id simply affects 0 rows — no error is raised."""
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
