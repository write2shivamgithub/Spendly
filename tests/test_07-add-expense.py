"""
tests/test_07-add-expense.py

Spec: Step 7 — Add Expense feature.

Tests are based solely on the feature specification for /expenses/add (GET + POST)
and the insert_expense query helper. Every test is fully independent and seeds
its own minimal data.
"""

import sqlite3
import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module
from database.queries import insert_expense
from app import app as flask_app


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Isolated, empty SQLite database for each test."""
    db_file = str(tmp_path / "test_add_expense.db")
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
def client(test_db):
    """Flask test client wired to the isolated test database."""
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.test_client() as c:
        yield c


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _insert_user(db_file, name="Test User", email="test@spendly.com",
                 password="pass1234", created_at="2026-01-01 00:00:00"):
    """Insert a user and return their id."""
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), created_at),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def _login(client, email="test@spendly.com", password="pass1234"):
    """POST to /login and return the response."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _set_session(client, user_id):
    """Directly inject user_id into the Flask session without going through login."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _query_expenses(db_file, user_id):
    """Return all expense rows for a given user_id as a list of sqlite3.Row."""
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


# ------------------------------------------------------------------ #
# 1. Unit tests for insert_expense                                    #
# ------------------------------------------------------------------ #

class TestInsertExpense:
    def test_valid_insert_returns_row_id(self, test_db):
        """insert_expense with valid args must return a non-None integer row id."""
        user_id = _insert_user(test_db)
        row_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        assert row_id is not None, "insert_expense must return the new row id"
        assert isinstance(row_id, int), "Returned row id must be an integer"
        assert row_id > 0, "Returned row id must be a positive integer"

    def test_valid_insert_row_is_queryable(self, test_db):
        """After insert_expense, the row must be retrievable from the DB."""
        user_id = _insert_user(test_db)
        row_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (row_id,)).fetchone()
        conn.close()

        assert row is not None, "Inserted expense row must be queryable by returned id"
        assert row["user_id"] == user_id, "Stored user_id must match the argument"
        assert row["amount"] == 50.0, "Stored amount must match the argument"
        assert row["category"] == "Food", "Stored category must match the argument"
        assert row["date"] == "2026-03-20", "Stored date must match the argument"
        assert row["description"] == "Lunch", "Stored description must match the argument"

    def test_insert_with_none_description_stores_null(self, test_db):
        """insert_expense with description=None must store NULL in the DB."""
        user_id = _insert_user(test_db)
        row_id = insert_expense(user_id, 75.0, "Transport", "2026-03-21", None)

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (row_id,)).fetchone()
        conn.close()

        assert row is not None, "Expense with NULL description must still be inserted"
        assert row["description"] is None, (
            "description must be stored as NULL when None is passed to insert_expense"
        )

    def test_insert_increments_expense_count(self, test_db):
        """Two sequential inserts must produce two distinct rows in the DB."""
        user_id = _insert_user(test_db)
        id1 = insert_expense(user_id, 10.0, "Food", "2026-03-01", "First")
        id2 = insert_expense(user_id, 20.0, "Bills", "2026-03-02", "Second")

        assert id1 != id2, "Each call to insert_expense must return a unique row id"

        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 2, "Two inserted rows must be present in the DB"


# ------------------------------------------------------------------ #
# 2. GET /expenses/add — auth guard                                   #
# ------------------------------------------------------------------ #

class TestGetAddExpenseAuthGuard:
    def test_unauthenticated_get_returns_302(self, client):
        """GET /expenses/add without auth must return 302."""
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must return 302"
        )

    def test_unauthenticated_get_redirects_to_login(self, client):
        """GET /expenses/add without auth must redirect to /login."""
        response = client.get("/expenses/add")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET /expenses/add must redirect to /login"
        )


# ------------------------------------------------------------------ #
# 3. GET /expenses/add — authenticated                                #
# ------------------------------------------------------------------ #

class TestGetAddExpenseAuthenticated:
    @pytest.fixture(autouse=True)
    def _seed_and_login(self, client, test_db):
        self.user_id = _insert_user(test_db)
        _set_session(client, self.user_id)
        self.response = client.get("/expenses/add")

    def test_authenticated_get_returns_200(self):
        """GET /expenses/add while logged in must return 200."""
        assert self.response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_response_contains_form_with_post_method(self):
        """The page must contain a form element with method POST."""
        data = self.response.data.decode("utf-8").lower()
        assert "<form" in data, "Response must contain a <form> element"
        assert 'method="post"' in data or "method='post'" in data, (
            "Form must have method POST"
        )

    def test_response_contains_category_food(self):
        assert b"Food" in self.response.data, (
            "Category select must include 'Food'"
        )

    def test_response_contains_category_transport(self):
        assert b"Transport" in self.response.data, (
            "Category select must include 'Transport'"
        )

    def test_response_contains_category_bills(self):
        assert b"Bills" in self.response.data, (
            "Category select must include 'Bills'"
        )

    def test_response_contains_category_health(self):
        assert b"Health" in self.response.data, (
            "Category select must include 'Health'"
        )

    def test_response_contains_category_entertainment(self):
        assert b"Entertainment" in self.response.data, (
            "Category select must include 'Entertainment'"
        )

    def test_response_contains_category_shopping(self):
        assert b"Shopping" in self.response.data, (
            "Category select must include 'Shopping'"
        )

    def test_response_contains_category_other(self):
        assert b"Other" in self.response.data, (
            "Category select must include 'Other'"
        )

    def test_response_contains_all_seven_categories(self):
        """All 7 fixed categories must be present in the rendered form."""
        expected = [b"Food", b"Transport", b"Bills", b"Health",
                    b"Entertainment", b"Shopping", b"Other"]
        for category in expected:
            assert category in self.response.data, (
                f"Category '{category.decode()}' must be present in the add-expense form"
            )

    def test_response_contains_amount_field(self):
        """The form must contain an amount input field."""
        data = self.response.data.decode("utf-8")
        assert 'name="amount"' in data, "Form must contain an input with name='amount'"

    def test_response_contains_date_field(self):
        """The form must contain a date input field."""
        data = self.response.data.decode("utf-8")
        assert 'name="date"' in data, "Form must contain an input with name='date'"

    def test_response_contains_description_field(self):
        """The form must contain a description input field."""
        data = self.response.data.decode("utf-8")
        assert 'name="description"' in data, "Form must contain an input with name='description'"


# ------------------------------------------------------------------ #
# 4. POST /expenses/add — auth guard                                  #
# ------------------------------------------------------------------ #

class TestPostAddExpenseAuthGuard:
    def test_unauthenticated_post_returns_302(self, client):
        """POST /expenses/add without auth must return 302."""
        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must return 302"
        )

    def test_unauthenticated_post_redirects_to_login(self, client):
        """POST /expenses/add without auth must redirect to /login."""
        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST /expenses/add must redirect to /login"
        )


# ------------------------------------------------------------------ #
# 5. POST /expenses/add — valid data                                  #
# ------------------------------------------------------------------ #

class TestPostAddExpenseValidData:
    def test_valid_post_redirects_to_profile(self, client, test_db):
        """Valid POST /expenses/add must redirect to /profile (302)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })
        assert response.status_code == 302, (
            "Valid POST must return 302"
        )
        assert "/profile" in response.headers["Location"], (
            "Valid POST must redirect to /profile"
        )

    def test_valid_post_inserts_row_in_db(self, client, test_db):
        """Valid POST must create a new expense row in the database."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })

        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 1, "Exactly one expense row must be inserted"
        row = rows[0]
        assert row["amount"] == 50.0, "Stored amount must be 50.0"
        assert row["category"] == "Food", "Stored category must be 'Food'"
        assert row["date"] == "2026-03-20", "Stored date must be '2026-03-20'"
        assert row["description"] == "Lunch", "Stored description must be 'Lunch'"

    def test_valid_post_stores_correct_user_id(self, client, test_db):
        """Valid POST must associate the expense with the logged-in user."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "120.0",
            "category": "Bills",
            "date": "2026-04-01",
            "description": "Electricity",
        })

        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id, (
            "Inserted expense must belong to the currently logged-in user"
        )


# ------------------------------------------------------------------ #
# 6. POST /expenses/add — missing amount                              #
# ------------------------------------------------------------------ #

class TestPostAddExpenseMissingAmount:
    def test_missing_amount_returns_200(self, client, test_db):
        """POST with no amount field must re-render the form (200)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })
        assert response.status_code == 200, (
            "Missing amount must return 200 (re-render form)"
        )

    def test_missing_amount_shows_error_message(self, client, test_db):
        """POST with no amount must include an error message in the response."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })
        data = response.data.decode("utf-8").lower()
        assert "amount" in data or "error" in data or "required" in data, (
            "Response must contain an error message when amount is missing"
        )

    def test_missing_amount_does_not_insert_row(self, client, test_db):
        """POST with no amount must not insert any row in the DB."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        })
        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 0, "No expense row must be inserted when amount is missing"


# ------------------------------------------------------------------ #
# 7. POST /expenses/add — amount = 0                                  #
# ------------------------------------------------------------------ #

class TestPostAddExpenseZeroAmount:
    def test_zero_amount_returns_200(self, client, test_db):
        """POST with amount=0 must re-render the form (200)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        assert response.status_code == 200, (
            "Amount = 0 must return 200 (re-render form)"
        )

    def test_zero_amount_shows_error_message(self, client, test_db):
        """POST with amount=0 must include an error message in the response."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        data = response.data.decode("utf-8").lower()
        assert "amount" in data or "error" in data or "greater" in data or "0" in data, (
            "Response must contain an error message when amount is 0"
        )

    def test_zero_amount_does_not_insert_row(self, client, test_db):
        """POST with amount=0 must not insert any row in the DB."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 0, "No expense row must be inserted when amount is 0"

    def test_negative_amount_returns_200(self, client, test_db):
        """POST with a negative amount must also be rejected (amount must be > 0)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "-10",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        assert response.status_code == 200, (
            "Negative amount must return 200 (re-render form)"
        )


# ------------------------------------------------------------------ #
# 8. POST /expenses/add — non-numeric amount                          #
# ------------------------------------------------------------------ #

class TestPostAddExpenseNonNumericAmount:
    @pytest.mark.parametrize("bad_amount", ["abc", "twelve", "5.0x", "--", "  "])
    def test_non_numeric_amount_returns_200(self, client, test_db, bad_amount):
        """POST with a non-numeric amount must re-render the form (200)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        assert response.status_code == 200, (
            f"Non-numeric amount '{bad_amount}' must return 200 (re-render form)"
        )

    @pytest.mark.parametrize("bad_amount", ["abc", "twelve", "5.0x"])
    def test_non_numeric_amount_shows_error_message(self, client, test_db, bad_amount):
        """POST with a non-numeric amount must include an error in the response."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        data = response.data.decode("utf-8").lower()
        assert "amount" in data or "error" in data or "number" in data, (
            f"Response must contain an error message for non-numeric amount '{bad_amount}'"
        )

    def test_non_numeric_amount_does_not_insert_row(self, client, test_db):
        """POST with a non-numeric amount must not insert any row in the DB."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "not-a-number",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Test",
        })
        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 0, "No expense row must be inserted for non-numeric amount"


# ------------------------------------------------------------------ #
# 9. POST /expenses/add — invalid category                            #
# ------------------------------------------------------------------ #

class TestPostAddExpenseInvalidCategory:
    def test_invalid_category_rerenders_form(self, client, test_db):
        """POST with a category not in the fixed list must re-render the form with an error."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "InvalidCategory",
            "date": "2026-03-20",
            "description": "Test",
        })
        assert response.status_code == 200, (
            "POST with invalid category must re-render the form (200)"
        )
        assert b"category" in response.data.lower()

    def test_invalid_category_does_not_insert_row(self, client, test_db):
        """POST with invalid category must not insert any row in the DB."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "NotACategory",
            "date": "2026-03-20",
            "description": "Test",
        })
        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 0, "No expense row must be inserted for an invalid category"

    @pytest.mark.parametrize("bad_category", [
        "food",        # lowercase — exact-match required
        "FOOD",        # uppercase
        "",            # empty string
        "Snacks",      # plausible but not in the fixed list
        "Misc",        # similar to Other but not in the list
    ])
    def test_various_invalid_categories_rerender(self, client, test_db, bad_category):
        """Multiple invalid categories must all be rejected with a 200 re-render."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": bad_category,
            "date": "2026-03-20",
            "description": "Test",
        })
        assert response.status_code == 200, (
            f"Invalid category '{bad_category}' must re-render the form (200)"
        )


# ------------------------------------------------------------------ #
# 10. POST /expenses/add — invalid date string                        #
# ------------------------------------------------------------------ #

class TestPostAddExpenseInvalidDate:
    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "20-03-2026",   # wrong format (DD-MM-YYYY)
        "2026/03/20",   # slashes instead of dashes
        "2026-13-01",   # month 13 does not exist
        "2026-02-30",   # Feb 30 does not exist
        "",             # empty string
    ])
    def test_invalid_date_returns_200(self, client, test_db, bad_date):
        """POST with an invalid date string must re-render the form (200)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": bad_date,
            "description": "Test",
        })
        assert response.status_code == 200, (
            f"Invalid date '{bad_date}' must return 200 (re-render form)"
        )

    def test_invalid_date_shows_error_message(self, client, test_db):
        """POST with an invalid date must include an error message in the response."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": "not-a-date",
            "description": "Test",
        })
        data = response.data.decode("utf-8").lower()
        assert "date" in data or "error" in data or "valid" in data, (
            "Response must contain an error message when date is invalid"
        )

    def test_invalid_date_does_not_insert_row(self, client, test_db):
        """POST with invalid date must not insert any row in the DB."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "50.0",
            "category": "Food",
            "date": "not-a-date",
            "description": "Test",
        })
        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 0, "No expense row must be inserted for an invalid date"


# ------------------------------------------------------------------ #
# 11. POST /expenses/add — no description (optional field)            #
# ------------------------------------------------------------------ #

class TestPostAddExpenseNoDescription:
    def test_no_description_redirects_to_profile(self, client, test_db):
        """POST without a description must succeed and redirect to /profile (302)."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "80.0",
            "category": "Transport",
            "date": "2026-03-20",
            "description": "",
        })
        assert response.status_code == 302, (
            "POST without description must return 302"
        )
        assert "/profile" in response.headers["Location"], (
            "POST without description must redirect to /profile"
        )

    def test_no_description_inserts_row_with_null_description(self, client, test_db):
        """POST without description must insert a row with description = NULL."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        client.post("/expenses/add", data={
            "amount": "80.0",
            "category": "Transport",
            "date": "2026-03-20",
            "description": "",
        })

        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 1, "Exactly one expense row must be inserted"
        assert rows[0]["description"] is None, (
            "description must be stored as NULL when no description is submitted"
        )

    def test_whitespace_only_description_stores_null(self, client, test_db):
        """POST with whitespace-only description must be treated as no description."""
        user_id = _insert_user(test_db)
        _set_session(client, user_id)

        response = client.post("/expenses/add", data={
            "amount": "90.0",
            "category": "Health",
            "date": "2026-03-21",
            "description": "   ",  # whitespace only — spec says strip and store None if blank
        })
        assert response.status_code == 302, (
            "POST with whitespace-only description must redirect to /profile (302)"
        )

        rows = _query_expenses(test_db, user_id)
        assert len(rows) == 1, "One expense row must be inserted"
        assert rows[0]["description"] is None, (
            "Whitespace-only description must be stored as NULL after stripping"
        )


# ------------------------------------------------------------------ #
# 12. Template landmarks                                              #
# ------------------------------------------------------------------ #

class TestAddExpenseTemplateLandmarks:
    """Confirm the rendered page contains key UI elements specified in the spec."""

    @pytest.fixture(autouse=True)
    def _seed_and_get(self, client, test_db):
        user_id = _insert_user(test_db)
        _set_session(client, user_id)
        self.response = client.get("/expenses/add")

    def test_page_contains_category_select_element(self):
        """The form must include a <select> element for category."""
        data = self.response.data.decode("utf-8").lower()
        assert "<select" in data, "Page must contain a <select> element for category"

    def test_page_contains_submit_button(self):
        """The form must include a submit button."""
        data = self.response.data.decode("utf-8").lower()
        assert 'type="submit"' in data or "<button" in data, (
            "Page must contain a submit button"
        )

    def test_page_contains_cancel_link_to_profile(self):
        """The form must include a cancel link pointing back to /profile."""
        data = self.response.data.decode("utf-8")
        assert "/profile" in data, (
            "Page must contain a link back to /profile (cancel link)"
        )

    def test_page_does_not_use_usd_symbol(self):
        """The page must not display $ anywhere."""
        assert b"$" not in self.response.data, (
            "Currency must be ₹ (INR), never $ (USD)"
        )
