from database.queries import get_recent_transactions


def test_get_recent_transactions_with_expenses(seeded_user):
    txns = get_recent_transactions(seeded_user)
    assert len(txns) == 8
    assert txns[0]["date"] == "Aug 20, 2026"       # newest first
    assert txns[-1]["date"] == "Aug 2, 2026"        # oldest last, no leading zero
    for t in txns:
        assert set(t.keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_empty(empty_user):
    assert get_recent_transactions(empty_user) == []


def test_get_recent_transactions_respects_limit(seeded_user):
    assert len(get_recent_transactions(seeded_user, limit=3)) == 3
