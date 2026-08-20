from datetime import datetime

from database.queries import get_summary_stats, get_user_by_id


def test_get_user_by_id_valid(seeded_user):
    user = get_user_by_id(seeded_user)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    # SQLite's datetime('now') is UTC — compare against utcnow(), not local
    # now(), to avoid a flaky mismatch near a UTC day/month boundary.
    assert user["member_since"] == datetime.utcnow().strftime("%B %Y")


def test_get_user_by_id_missing(temp_db):
    assert get_user_by_id(999999) is None


def test_get_summary_stats_with_expenses(seeded_user):
    stats = get_summary_stats(seeded_user)
    # NOTE: the spec's Definition-of-done cites ₹346.24 for the seed user,
    # but the actual seed data in database/db.py sums to 384.21 (verified
    # by hand). This test asserts the correct value for the real seed data;
    # the spec's number is stale.
    assert stats["total_spent"] == 384.21
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_empty(empty_user):
    assert get_summary_stats(empty_user) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }
