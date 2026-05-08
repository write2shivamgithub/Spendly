import pytest
import sqlite3
from werkzeug.security import generate_password_hash
import database.db as db_module
from app import app as flask_app


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        CREATE TABLE users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE expenses (
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
    return db_file


@pytest.fixture
def user_with_expenses(test_db):
    """User with 5 expenses across 4 categories. Total = ₹580.00. Top category = Bills (₹450.00)."""
    conn = sqlite3.connect(test_db)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Test User", "test@spendly.com", generate_password_hash("pass1234"), "2026-01-15 10:00:00"),
    )
    user_id = cursor.lastrowid
    expenses = [
        (300.00, "Bills",         "2026-04-10", "Electricity"),
        (150.00, "Bills",         "2026-04-05", "Internet"),
        (80.00,  "Food",          "2026-04-08", "Groceries"),
        (30.00,  "Transport",     "2026-04-01", "Bus pass"),
        (20.00,  "Entertainment", "2026-03-28", "Movie"),
    ]
    for amount, category, date, desc in expenses:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, desc),
        )
    conn.commit()
    conn.close()
    return user_id


@pytest.fixture
def user_no_expenses(test_db):
    """User with zero expenses. created_at = 2026-03-01."""
    conn = sqlite3.connect(test_db)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Empty User", "empty@spendly.com", generate_password_hash("pass1234"), "2026-03-01 10:00:00"),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


@pytest.fixture
def client():
    """Flask test client backed by the real seed database."""
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.test_client() as c:
        yield c
