import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'spendly.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("demo@spendly.com",)
    ).fetchone()

    if existing:
        user_id = existing["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo1234"))
        )
        user_id = cursor.lastrowid

    sample_expenses = [
        (45.00,  "Food",          "2026-04-01", "Grocery run"),
        (120.00, "Bills",         "2026-04-03", "Electricity bill"),
        (15.50,  "Transport",     "2026-04-05", "Bus pass top-up"),
        (60.00,  "Health",        "2026-04-08", "Pharmacy"),
        (200.00, "Bills",         "2026-04-10", "Internet subscription"),
        (35.00,  "Food",          "2026-04-14", "Restaurant lunch"),
        (80.00,  "Transport",     "2026-04-18", "Taxi rides"),
        (25.00,  "Entertainment", "2026-04-22", "Movie tickets"),
    ]

    for amount, category, date, description in sample_expenses:
        row = conn.execute(
            "SELECT id FROM expenses WHERE user_id = ? AND date = ? AND category = ?",
            (user_id, date, category)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date, description)
            )

    conn.commit()
    conn.close()
