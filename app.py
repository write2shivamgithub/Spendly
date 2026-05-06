import sqlite3

from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # TODO: load from env in production


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

    profile_user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "01 Jan 2025",
    }
    stats = {
        "total_spent": "₹580.50",
        "transaction_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "22 Apr 2026", "description": "Movie tickets",         "category": "Entertainment", "amount": "₹25.00"},
        {"date": "18 Apr 2026", "description": "Taxi rides",            "category": "Transport",     "amount": "₹80.00"},
        {"date": "14 Apr 2026", "description": "Restaurant lunch",      "category": "Food",          "amount": "₹35.00"},
        {"date": "10 Apr 2026", "description": "Internet subscription", "category": "Bills",         "amount": "₹200.00"},
        {"date": "08 Apr 2026", "description": "Pharmacy",              "category": "Health",        "amount": "₹60.00"},
    ]
    category_breakdown = [
        {"category": "Bills",         "total": "₹320.00", "percent": 55},
        {"category": "Transport",     "total": "₹95.50",  "percent": 16},
        {"category": "Food",          "total": "₹80.00",  "percent": 14},
        {"category": "Health",        "total": "₹60.00",  "percent": 10},
        {"category": "Entertainment", "total": "₹25.00",  "percent": 4},
    ]
    return render_template(
        "profile.html",
        profile_user=profile_user,
        stats=stats,
        transactions=transactions,
        category_breakdown=category_breakdown,
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


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
