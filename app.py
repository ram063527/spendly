import math
import sqlite3
from datetime import date, datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    insert_expense,
    remove_expense,
    update_expense,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key"

EXPENSE_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("Email already registered.", "error")
            return render_template("register.html")

        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("login"))

    abort(405)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["user_initials"] = "".join(part[0] for part in user["name"].split()[:2]).upper()
        return redirect(url_for("profile"))

    abort(405)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

def _shift_months_back(d, months):
    """Returns the first of the month `months` calendar months before d."""
    month_index = d.month - 1 - months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _date_presets(today):
    return {
        "this_month": (today.replace(day=1).isoformat(), today.isoformat()),
        "last_3_months": (_shift_months_back(today, 2).isoformat(), today.isoformat()),
        "last_6_months": (_shift_months_back(today, 5).isoformat(), today.isoformat()),
    }


def _parse_date_arg(raw_value):
    if not raw_value:
        return None
    try:
        datetime.strptime(raw_value, "%Y-%m-%d")
    except ValueError:
        return None
    return raw_value


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    date_from = _parse_date_arg(request.args.get("date_from"))
    date_to = _parse_date_arg(request.args.get("date_to"))

    if date_from is not None and date_to is not None and date_from > date_to:
        date_from, date_to = None, None
        flash("Start date must be before end date.", "error")

    presets = _date_presets(date.today())

    active_preset = None
    if date_from is None and date_to is None:
        active_preset = "all_time"
    else:
        for name, (preset_from, preset_to) in presets.items():
            if date_from == preset_from and date_to == preset_to:
                active_preset = name
                break

    stats = get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    categories = get_category_breakdown(user_id, date_from=date_from, date_to=date_to)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        date_from=date_from,
        date_to=date_to,
        active_preset=active_preset,
        presets=presets,
    )


def _parse_expense_form(form):
    """Validates the add/edit expense form fields. Returns (expense_dict, error_message);
    error_message is None on success."""
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    date_raw = form.get("date", "").strip()
    description = form.get("description", "").strip()[:200]

    try:
        amount = float(amount_raw)
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError
    except ValueError:
        return None, "Enter a valid amount greater than 0."

    if category not in EXPENSE_CATEGORIES:
        return None, "Select a valid category."

    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except ValueError:
        return None, "Enter a valid date."

    return {"amount": amount, "category": category, "date": date_raw, "description": description or None}, None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    today = date.today().isoformat()

    def render_form():
        return render_template("add_expense.html", categories=EXPENSE_CATEGORIES, today=today)

    if request.method == "GET":
        return render_form()

    if request.method == "POST":
        expense, error = _parse_expense_form(request.form)
        if error:
            flash(error, "error")
            return render_form()

        insert_expense(user_id, expense["amount"], expense["category"], expense["date"], expense["description"])
        flash("Expense added.", "success")
        return redirect(url_for("profile"))

    abort(405)


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    def render_form():
        return render_template("edit_expense.html", expense=expense, categories=EXPENSE_CATEGORIES)

    if request.method == "GET":
        return render_form()

    if request.method == "POST":
        expense_data, error = _parse_expense_form(request.form)
        if error:
            flash(error, "error")
            return render_form()

        update_expense(
            id, user_id, expense_data["amount"], expense_data["category"],
            expense_data["date"], expense_data["description"],
        )
        flash("Expense updated.", "success")
        return redirect(url_for("profile"))

    abort(405)


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    remove_expense(id, user_id)
    flash("Expense deleted.", "success")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
