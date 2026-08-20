import sqlite3

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key"

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


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Step 4 = static UI. Step 5 replaces these literals with real queries
    # scoped to session["user_id"]; key names/shapes stay stable so
    # profile.html needs no changes when that happens.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "November 2025",
    }

    stats = {
        "total_spent": 384.21,
        "transaction_count": 8,
        "top_category": "Bills",
    }

    transactions = [
        {"date": "Aug 20, 2026", "description": "Miscellaneous purchase", "category": "Other", "amount": 15.00},
        {"date": "Aug 17, 2026", "description": "Dinner at restaurant", "category": "Food", "amount": 47.60},
        {"date": "Aug 14, 2026", "description": "New running shoes", "category": "Shopping", "amount": 65.99},
        {"date": "Aug 11, 2026", "description": "Movie tickets", "category": "Entertainment", "amount": 28.00},
        {"date": "Aug 8, 2026", "description": "Pharmacy purchase", "category": "Health", "amount": 22.15},
        {"date": "Aug 5, 2026", "description": "Electricity bill", "category": "Bills", "amount": 112.40},
        {"date": "Aug 4, 2026", "description": "Gas fill-up", "category": "Transport", "amount": 38.75},
        {"date": "Aug 2, 2026", "description": "Weekly groceries", "category": "Food", "amount": 54.32},
    ]

    categories = [
        {"name": "Bills", "amount": 112.40},
        {"name": "Food", "amount": 101.92},
        {"name": "Shopping", "amount": 65.99},
        {"name": "Transport", "amount": 38.75},
        {"name": "Entertainment", "amount": 28.00},
        {"name": "Health", "amount": 22.15},
        {"name": "Other", "amount": 15.00},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
