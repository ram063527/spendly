"""Pure query helpers for the profile page. No Flask imports — callers
(routes) pass in a user_id and get back plain dicts/lists. Each function
opens its own connection via get_db() and closes it before returning,
matching the convention in database/db.py."""

from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Subagent 2 (Summary) implements this.
    Returns dict with name, email, member_since ("Month YYYY", derived from
    users.created_at), or None if no such user."""
    raise NotImplementedError


def get_summary_stats(user_id):
    """Subagent 2 (Summary) implements this.
    Returns dict with total_spent, transaction_count, top_category.
    No expenses -> {"total_spent": 0, "transaction_count": 0, "top_category": "—"}."""
    raise NotImplementedError


def get_recent_transactions(user_id, limit=10):
    """Subagent 1 (Transactions) implements this.
    Returns list of dicts (date, description, category, amount), newest first.
    No expenses -> []."""
    raise NotImplementedError


def get_category_breakdown(user_id):
    """Subagent 3 (Categories) implements this.
    Returns list of dicts (name, amount, pct), ordered by amount desc.
    pct values are ints summing to 100 (largest category absorbs rounding
    remainder). No expenses -> []."""
    raise NotImplementedError
