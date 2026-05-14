import math
import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
    insert_expense,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # TODO: load from env in production

VALID_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html", user=None)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")
    confirm_password = request.form.get("confirm_password", "").strip()
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")
    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")

    pw_hash = generate_password_hash(password)
    try:
        user_id = create_user(name, email, pw_hash)
    except sqlite3.IntegrityError:
        return render_template("register.html", error="An account with that email already exists.")

    session["user_id"] = user_id
    session["user_name"] = name
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    raw_from = request.args.get("from", "").strip()
    raw_to = request.args.get("to", "").strip()

    date_from = date_to = None
    dt_from = dt_to = None
    try:
        if raw_from and raw_to:
            dt_from = datetime.strptime(raw_from, "%Y-%m-%d")
            dt_to = datetime.strptime(raw_to, "%Y-%m-%d")
            if dt_from <= dt_to:
                date_from, date_to = raw_from, raw_to
    except ValueError:
        pass

    filter_label = None
    if date_from and dt_from and dt_to:
        filter_label = dt_from.strftime("%d %b %Y") + " – " + dt_to.strftime("%d %b %Y")

    profile_user = get_user_by_id(session["user_id"])
    stats = get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(session["user_id"], date_from=date_from, date_to=date_to)
    category_breakdown = get_category_breakdown(session["user_id"], date_from=date_from, date_to=date_to)
    return render_template(
        "profile.html",
        profile_user=profile_user,
        stats=stats,
        transactions=transactions,
        category_breakdown=category_breakdown,
        date_from=date_from,
        date_to=date_to,
        filter_label=filter_label,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = datetime.today().strftime("%Y-%m-%d")

    if request.method == "GET":
        return render_template("add_expense.html", categories=VALID_CATEGORIES, today=today)

    amount_str = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date_str = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip() or None

    def rerender(error):
        return render_template(
            "add_expense.html",
            categories=VALID_CATEGORIES,
            today=today,
            error=error,
        )

    try:
        amount = float(amount_str)
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError
    except ValueError:
        return rerender("Amount must be a number greater than 0.")

    if category not in VALID_CATEGORIES:
        return rerender("Please select a valid category.")

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return rerender("Date must be a valid date (YYYY-MM-DD).")

    if description and len(description) > 200:
        return rerender("Description must be 200 characters or fewer.")

    insert_expense(session["user_id"], amount, category, date_str, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    import os
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5001)
