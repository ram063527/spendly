"""Tests for Step 6: Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile-page.md

Query-layer tests call database.queries.get_summary_stats /
get_recent_transactions / get_category_breakdown directly with
date_from/date_to, using the seeded_user/empty_user fixtures from
conftest.py.

Route-layer tests drive GET /profile through the Flask test client,
logged in as the seeded_user/empty_user fixture's demo account (not the
app's real global seed data), so assertions are deterministic.

NOTE on dates: seeded_user's 8 expenses fall on 2026-08-02 .. 2026-08-20
(see conftest.py), which lines up with this environment's "today"
(2026-08-20, per CLAUDE.md/system context) the same way database/db.py's
real seed_db() always seeds relative to date.today(). Preset-window tests
("This Month" / "Last 3 Months" / "Last 6 Months") use a locally-built
multi_month_user fixture with expenses spread across widely separated
months (this month / ~2 months back / ~5 months back / >1 year back) so
that inclusion/exclusion is unambiguous regardless of whether the app
computes "N months back" via calendar-month or day-count arithmetic.
"""

import html
import re

import pytest

from app import app as flask_app
from database.queries import get_category_breakdown, get_recent_transactions, get_summary_stats

SEEDED_EMAIL = "demo@spendly.com"
SEEDED_PASSWORD = "demo123"
EMPTY_EMAIL = "empty@spendly.com"
EMPTY_PASSWORD = "pw12345"
MULTI_MONTH_EMAIL = "multimonth@spendly.com"
MULTI_MONTH_PASSWORD = "pw12345"

INVALID_RANGE_FLASH = "Start date must be before end date."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(temp_db):
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture
def multi_month_user(temp_db):
    """User whose expenses span this month, ~2 months back, ~5 months
    back, and >1 year back. Used to prove presets truly exclude
    out-of-window expenses, unlike seeded_user whose data all clusters
    inside a single 19-day window."""
    from werkzeug.security import generate_password_hash

    conn = temp_db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Multi Month User", MULTI_MONTH_EMAIL, generate_password_hash(MULTI_MONTH_PASSWORD)),
        )
        user_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 10.00, "Food", "2026-08-10", "this month expense"),
                (user_id, 20.00, "Transport", "2026-06-15", "two months back expense"),
                (user_id, 30.00, "Bills", "2026-03-01", "five months back expense"),
                (user_id, 40.00, "Health", "2025-01-15", "over a year back expense"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return user_id


def _login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Black-box HTML helpers (no reliance on implementation internals — only on
# the observable contract that presets render as <a href="...">Label</a>
# links and the custom-range fields render as <input name="date_from"/...>)
# ---------------------------------------------------------------------------

_ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_INPUT_RE = re.compile(r"<input\b([^>]*)/?>", re.IGNORECASE)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def _find_preset_anchor(body, label):
    """Locate the <a> tag whose visible text equals `label` (e.g. "This
    Month"). Returns (attrs_string, href) or (None, None) if not found.
    Tolerant of nested markup/whitespace inside the anchor and of
    attribute ordering."""
    for attrs, inner in _ANCHOR_RE.findall(body):
        text = " ".join(_TAG_STRIP_RE.sub("", inner).split())
        if text == label:
            href_match = re.search(r'href="([^"]*)"', attrs)
            href = html.unescape(href_match.group(1)) if href_match else None
            return attrs, href
    return None, None


def _find_input_value(body, name):
    """Returns the `value` attribute of the <input> with the given `name`,
    "" if the attribute is absent, or None if no such input exists."""
    for attrs in _INPUT_RE.findall(body):
        name_match = re.search(r'name="([^"]*)"', attrs)
        if name_match and name_match.group(1) == name:
            value_match = re.search(r'value="([^"]*)"', attrs)
            return value_match.group(1) if value_match else ""
    return None


# ---------------------------------------------------------------------------
# Query-layer tests: get_summary_stats
# ---------------------------------------------------------------------------


def test_get_summary_stats_no_filter_matches_unfiltered(seeded_user):
    assert get_summary_stats(seeded_user, date_from=None, date_to=None) == get_summary_stats(seeded_user)


def test_get_summary_stats_date_range_filters_correctly(seeded_user):
    stats = get_summary_stats(seeded_user, date_from="2026-08-02", date_to="2026-08-08")
    # In-range: Food 54.32 (Aug 2), Transport 38.75 (Aug 4), Bills 112.40
    # (Aug 5), Health 22.15 (Aug 8) = 227.62, 4 rows, Bills is largest.
    assert stats["total_spent"] == 227.62
    assert stats["transaction_count"] == 4
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_date_range_no_matches(seeded_user):
    stats = get_summary_stats(seeded_user, date_from="2020-01-01", date_to="2020-01-31")
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def test_get_summary_stats_only_one_bound_is_treated_as_unfiltered(seeded_user):
    # Spec: filter applies "when both are provided" — a single bound must
    # not silently filter anything.
    stats = get_summary_stats(seeded_user, date_from="2026-08-02", date_to=None)
    assert stats == get_summary_stats(seeded_user)


def test_get_summary_stats_empty_user_date_range(empty_user):
    stats = get_summary_stats(empty_user, date_from="2026-08-01", date_to="2026-08-31")
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


# ---------------------------------------------------------------------------
# Query-layer tests: get_recent_transactions
# ---------------------------------------------------------------------------


def test_get_recent_transactions_no_filter_matches_unfiltered(seeded_user):
    assert get_recent_transactions(seeded_user, date_from=None, date_to=None) == get_recent_transactions(seeded_user)


def test_get_recent_transactions_date_range_filters_correctly(seeded_user):
    txns = get_recent_transactions(seeded_user, date_from="2026-08-02", date_to="2026-08-08")
    assert len(txns) == 4
    assert txns[0]["date"] == "Aug 8, 2026"  # newest first, within range
    assert txns[-1]["date"] == "Aug 2, 2026"  # oldest last, within range
    descriptions = {t["description"] for t in txns}
    assert descriptions == {"Weekly groceries", "Gas fill-up", "Electricity bill", "Pharmacy purchase"}


def test_get_recent_transactions_date_range_no_matches(seeded_user):
    assert get_recent_transactions(seeded_user, date_from="2020-01-01", date_to="2020-01-31") == []


def test_get_recent_transactions_date_range_respects_limit(seeded_user):
    txns = get_recent_transactions(seeded_user, limit=2, date_from="2026-08-02", date_to="2026-08-20")
    assert len(txns) == 2


# ---------------------------------------------------------------------------
# Query-layer tests: get_category_breakdown
# ---------------------------------------------------------------------------


def test_get_category_breakdown_no_filter_matches_unfiltered(seeded_user):
    assert get_category_breakdown(seeded_user, date_from=None, date_to=None) == get_category_breakdown(seeded_user)


def test_get_category_breakdown_date_range_filters_correctly(seeded_user):
    cats = get_category_breakdown(seeded_user, date_from="2026-08-02", date_to="2026-08-08")
    assert len(cats) == 4
    assert {c["name"] for c in cats} == {"Food", "Transport", "Bills", "Health"}
    assert cats[0]["name"] == "Bills"
    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_date_range_no_matches(seeded_user):
    assert get_category_breakdown(seeded_user, date_from="2020-01-01", date_to="2020-01-31") == []


# ---------------------------------------------------------------------------
# Route-layer tests: unfiltered behavior unchanged from Step 5
# ---------------------------------------------------------------------------


def test_profile_unfiltered_matches_step5_totals(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹384.21" in body
    assert "Bills" in body
    for category in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert category in body


def test_profile_unfiltered_empty_user_shows_zero_state(client, empty_user):
    _login(client, EMPTY_EMAIL, EMPTY_PASSWORD)
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "₹0.00" in resp.get_data(as_text=True)


def test_profile_redirects_when_unauthenticated(client):
    resp = client.get("/profile?date_from=2026-08-01&date_to=2026-08-31")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Route-layer tests: custom range filtering
# ---------------------------------------------------------------------------


def test_profile_custom_range_filters_all_three_sections(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=2026-08-02&date_to=2026-08-08")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Summary stats reflect only the 4 in-range expenses.
    assert "₹227.62" in body

    # Transactions: in-range descriptions present, out-of-range absent.
    for description in ["Weekly groceries", "Gas fill-up", "Electricity bill", "Pharmacy purchase"]:
        assert description in body, f"Expected in-range transaction {description!r} in filtered profile page"
    for description in ["Movie tickets", "New running shoes", "Dinner at restaurant", "Miscellaneous purchase"]:
        assert description not in body, f"Did not expect out-of-range transaction {description!r} in filtered profile page"

    # Category breakdown: in-range categories present.
    for category in ["Food", "Transport", "Bills", "Health"]:
        assert category in body


def test_profile_custom_range_single_day_is_valid(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=2026-08-05&date_to=2026-08-05")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹112.40" in body
    assert "Electricity bill" in body
    assert INVALID_RANGE_FLASH not in body


def test_profile_custom_range_zero_matches_shows_empty_state(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹0.00" in body
    for description in ["Weekly groceries", "Gas fill-up", "Electricity bill", "Pharmacy purchase",
                         "Movie tickets", "New running shoes", "Dinner at restaurant", "Miscellaneous purchase"]:
        assert description not in body


def test_profile_custom_range_prefills_date_inputs(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=2026-08-02&date_to=2026-08-08")
    body = resp.get_data(as_text=True)
    assert _find_input_value(body, "date_from") == "2026-08-02"
    assert _find_input_value(body, "date_to") == "2026-08-08"


def test_profile_unfiltered_date_inputs_are_not_prefilled(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    for name in ("date_from", "date_to"):
        value = _find_input_value(body, name)
        assert value in (None, ""), f"Expected no prefilled {name!r} value when unfiltered, got {value!r}"


# ---------------------------------------------------------------------------
# Route-layer tests: invalid / malformed input falls back gracefully
# ---------------------------------------------------------------------------


def test_profile_invalid_range_flashes_error_and_falls_back(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=2026-08-10&date_to=2026-08-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert INVALID_RANGE_FLASH in body
    # Falls back to the full unfiltered totals.
    assert "₹384.21" in body
    for category in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert category in body


def test_profile_malformed_date_string_does_not_crash(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=not-a-date&date_to=2026-08-08")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹384.21" in body  # silently falls back to unfiltered


def test_profile_both_dates_malformed_does_not_crash(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=not-a-date&date_to=also-not-a-date")
    assert resp.status_code == 200
    assert "₹384.21" in resp.get_data(as_text=True)


def test_profile_single_bound_without_other_falls_back_unfiltered(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=2026-08-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹384.21" in body
    assert INVALID_RANGE_FLASH not in body


def test_profile_empty_string_params_do_not_crash(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get("/profile?date_from=&date_to=")
    assert resp.status_code == 200
    assert "₹384.21" in resp.get_data(as_text=True)


def test_profile_sql_injection_attempt_does_not_crash_or_alter_data(client, seeded_user, temp_db):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    resp = client.get(
        "/profile",
        query_string={"date_from": "'; DROP TABLE expenses; --", "date_to": "2026-08-08"},
    )
    assert resp.status_code == 200
    assert "₹384.21" in resp.get_data(as_text=True)  # falls back unfiltered, nothing dropped

    conn = temp_db.get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (seeded_user,)).fetchone()[0]
    finally:
        conn.close()
    assert count == 8


# ---------------------------------------------------------------------------
# Route-layer tests: preset buttons render as navigable links
# ---------------------------------------------------------------------------


def test_profile_filter_bar_has_all_four_presets(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    body = client.get("/profile").get_data(as_text=True)
    for label in ["This Month", "Last 3 Months", "Last 6 Months", "All Time"]:
        _, href = _find_preset_anchor(body, label)
        assert href is not None, f"Expected a link labelled {label!r} on the profile page"


def test_profile_all_time_preset_link_has_no_query_params(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    body = client.get("/profile?date_from=2026-08-02&date_to=2026-08-08").get_data(as_text=True)
    _, href = _find_preset_anchor(body, "All Time")
    assert href is not None
    assert "?" not in href, f"'All Time' link should carry no query params, got {href!r}"


# ---------------------------------------------------------------------------
# Route-layer tests: presets actually filter (using multi_month_user, whose
# expenses are spread far enough apart that any reasonable "N months back"
# arithmetic produces the same inclusion/exclusion result)
# ---------------------------------------------------------------------------


def _get_preset_href(client, label):
    body = client.get("/profile").get_data(as_text=True)
    _, href = _find_preset_anchor(body, label)
    assert href is not None, f"Expected a link labelled {label!r} on the profile page"
    return href


def test_this_month_preset_excludes_older_expenses(client, multi_month_user):
    _login(client, MULTI_MONTH_EMAIL, MULTI_MONTH_PASSWORD)
    href = _get_preset_href(client, "This Month")
    body = client.get(href).get_data(as_text=True)

    assert "this month expense" in body
    assert "two months back expense" not in body
    assert "five months back expense" not in body
    assert "over a year back expense" not in body
    assert "₹10.00" in body


def test_last_3_months_preset_includes_recent_excludes_older(client, multi_month_user):
    _login(client, MULTI_MONTH_EMAIL, MULTI_MONTH_PASSWORD)
    href = _get_preset_href(client, "Last 3 Months")
    body = client.get(href).get_data(as_text=True)

    assert "this month expense" in body
    assert "two months back expense" in body
    assert "five months back expense" not in body
    assert "over a year back expense" not in body
    assert "₹30.00" in body


def test_last_6_months_preset_includes_mid_range_excludes_old(client, multi_month_user):
    _login(client, MULTI_MONTH_EMAIL, MULTI_MONTH_PASSWORD)
    href = _get_preset_href(client, "Last 6 Months")
    body = client.get(href).get_data(as_text=True)

    assert "this month expense" in body
    assert "two months back expense" in body
    assert "five months back expense" in body
    assert "over a year back expense" not in body
    assert "₹60.00" in body


def test_all_time_preset_includes_everything(client, multi_month_user):
    _login(client, MULTI_MONTH_EMAIL, MULTI_MONTH_PASSWORD)
    href = _get_preset_href(client, "All Time")
    body = client.get(href).get_data(as_text=True)

    for description in [
        "this month expense",
        "two months back expense",
        "five months back expense",
        "over a year back expense",
    ]:
        assert description in body
    assert "₹100.00" in body


# ---------------------------------------------------------------------------
# Route-layer tests: active preset / range is visually indicated
# ---------------------------------------------------------------------------


def test_all_time_is_visually_marked_active_by_default(client, seeded_user):
    _login(client, SEEDED_EMAIL, SEEDED_PASSWORD)
    unfiltered_body = client.get("/profile").get_data(as_text=True)
    filtered_body = client.get("/profile?date_from=2026-08-02&date_to=2026-08-08").get_data(as_text=True)

    attrs_when_default, _ = _find_preset_anchor(unfiltered_body, "All Time")
    attrs_when_filtered, _ = _find_preset_anchor(filtered_body, "All Time")
    assert attrs_when_default is not None and attrs_when_filtered is not None
    assert attrs_when_default != attrs_when_filtered, (
        "Expected the 'All Time' preset's markup (e.g. an active CSS class) "
        "to differ between the unfiltered (active) and filtered (inactive) states"
    )


def test_this_month_preset_is_visually_marked_active_when_applied(client, multi_month_user):
    _login(client, MULTI_MONTH_EMAIL, MULTI_MONTH_PASSWORD)
    unfiltered_body = client.get("/profile").get_data(as_text=True)
    attrs_inactive, href = _find_preset_anchor(unfiltered_body, "This Month")
    assert href is not None

    active_body = client.get(href).get_data(as_text=True)
    attrs_active, _ = _find_preset_anchor(active_body, "This Month")
    assert attrs_inactive is not None and attrs_active is not None
    assert attrs_active != attrs_inactive, (
        "Expected the 'This Month' preset's markup to change once it "
        "becomes the active filter"
    )
