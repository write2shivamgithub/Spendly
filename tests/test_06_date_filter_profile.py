"""
tests/test_06_date_filter_profile.py

Spec: Step 6 — Date-range filter for the /profile page.

Tests are based solely on the feature specification, not the implementation.
Every test is fully independent and seeds its own minimal data.
"""

import sqlite3
import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module
from app import app as flask_app


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Isolated, empty SQLite database for each test."""
    db_file = str(tmp_path / "test_filter.db")
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


def _insert_user(db_file, name="Filter User", email="filter@spendly.com",
                 password="pass1234", created_at="2026-01-01 00:00:00"):
    """Helper: insert a user and return their id."""
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


def _insert_expenses(db_file, user_id, expenses):
    """Helper: insert a list of (amount, category, date, description) tuples."""
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    for amount, category, date, description in expenses:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
    conn.commit()
    conn.close()


def _login(client, email="filter@spendly.com", password="pass1234"):
    """Helper: POST to /login and return the response."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ------------------------------------------------------------------ #
# 1. Auth guard                                                       #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_unauthenticated_get_profile_redirects_302(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile must return 302"
        )

    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert "/login" in response.headers["Location"], (
            "Redirect must point to /login"
        )

    def test_unauthenticated_get_profile_with_filter_params_redirects(self, client):
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        assert response.status_code == 302, (
            "Unauthenticated request with filter params must also redirect"
        )
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# 2. No-filter (all-time) view                                        #
# ------------------------------------------------------------------ #

class TestNoFilterAllTime:
    def test_profile_no_params_returns_200(self, client, test_db):
        user_id = _insert_user(test_db)
        _login(client)
        response = client.get("/profile")
        assert response.status_code == 200, (
            "GET /profile with no params must return 200"
        )

    def test_profile_no_params_no_filter_label(self, client, test_db):
        user_id = _insert_user(test_db)
        _insert_expenses(test_db, user_id, [
            (100.00, "Food", "2026-04-01", "Lunch"),
        ])
        _login(client)
        response = client.get("/profile")
        assert b"Filtered:" not in response.data, (
            "No filter label should appear when no query params are given"
        )

    def test_profile_no_params_shows_all_time_stats(self, client, test_db):
        user_id = _insert_user(test_db)
        _insert_expenses(test_db, user_id, [
            (100.00, "Food",      "2026-03-15", "March food"),
            (200.00, "Bills",     "2026-04-10", "April bill"),
            (50.00,  "Transport", "2026-05-01", "May transport"),
        ])
        _login(client)
        response = client.get("/profile")
        data = response.data
        # All three months of data must be present: total = ₹350.00, 3 transactions
        assert b"\xe2\x82\xb9350.00" in data, (
            "All-time total must include all expenses across all dates"
        )

    def test_profile_no_params_renders_profile_page(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile")
        assert b"My Profile" in response.data, (
            "Profile page heading must be present"
        )


# ------------------------------------------------------------------ #
# 3. Valid date-range filter                                          #
# ------------------------------------------------------------------ #

class TestValidDateRangeFilter:
    """Expenses: two in April, one in March. Filter to April only."""

    @pytest.fixture(autouse=True)
    def _seed(self, client, test_db):
        self.user_id = _insert_user(test_db)
        _insert_expenses(test_db, self.user_id, [
            (300.00, "Bills",     "2026-04-05", "Electricity"),
            (100.00, "Food",      "2026-04-20", "Groceries"),
            (50.00,  "Transport", "2026-03-10", "Bus pass"),  # outside range
        ])
        _login(client)
        self.response = client.get("/profile?from=2026-04-01&to=2026-04-30")

    def test_returns_200(self):
        assert self.response.status_code == 200, (
            "Valid filter range must return 200"
        )

    def test_filtered_total_excludes_out_of_range_expense(self):
        # April only: 300 + 100 = 400. March expense (50) must be excluded.
        assert b"\xe2\x82\xb9400.00" in self.response.data, (
            "Filtered total must be ₹400.00 (only April expenses)"
        )

    def test_filtered_transaction_count(self):
        # 2 transactions in April
        assert b"2" in self.response.data, (
            "Transaction count must reflect only in-range expenses"
        )

    def test_filtered_top_category_is_bills(self):
        assert b"Bills" in self.response.data, (
            "Top category within the filtered range must be Bills"
        )

    def test_out_of_range_description_not_in_transactions(self):
        assert b"Bus pass" not in self.response.data, (
            "Transaction outside the filter range must not appear in the transaction list"
        )

    def test_in_range_descriptions_appear_in_transactions(self):
        assert b"Electricity" in self.response.data, (
            "In-range transaction description must appear in the response"
        )
        assert b"Groceries" in self.response.data, (
            "In-range transaction description must appear in the response"
        )

    def test_filter_label_is_visible(self):
        assert b"Filtered:" in self.response.data, (
            "Active-filter label must be visible when a valid range is applied"
        )

    def test_filter_label_contains_from_date(self):
        # Formatted as DD Mon YYYY per spec: "01 Apr 2026"
        assert b"01 Apr 2026" in self.response.data, (
            "Filter label must contain the from-date formatted as DD Mon YYYY"
        )

    def test_filter_label_contains_to_date(self):
        assert b"30 Apr 2026" in self.response.data, (
            "Filter label must contain the to-date formatted as DD Mon YYYY"
        )

    def test_category_breakdown_excludes_out_of_range_category(self):
        # Transport only had an expense in March; it must not appear in breakdown
        assert b"Transport" not in self.response.data, (
            "Category breakdown must exclude categories with no in-range expenses"
        )

    def test_currency_symbol_is_rupee(self):
        # INR rupee sign ₹ is \xe2\x82\xb9 in UTF-8
        assert b"\xe2\x82\xb9" in self.response.data, (
            "All amounts must display the ₹ symbol, not $ or £"
        )
        assert b"$" not in self.response.data
        assert b"\xc2\xa3" not in self.response.data  # £


# ------------------------------------------------------------------ #
# 4. Form pre-fill                                                    #
# ------------------------------------------------------------------ #

class TestFormPrefill:
    def test_from_input_is_prefilled(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        assert b'value="2026-04-01"' in response.data, (
            "The 'from' date input must be pre-filled with the active from-date"
        )

    def test_to_input_is_prefilled(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        assert b'value="2026-04-30"' in response.data, (
            "The 'to' date input must be pre-filled with the active to-date"
        )

    def test_inputs_are_empty_when_no_filter(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile")
        # Both inputs should have empty value attributes
        assert b'value="2026-' not in response.data, (
            "Date inputs must not be pre-filled when no filter is active"
        )


# ------------------------------------------------------------------ #
# 5. Clear link                                                       #
# ------------------------------------------------------------------ #

class TestClearLink:
    def test_clear_link_present_without_filter(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile")
        # The clear link must exist on the page regardless of filter state
        assert b"Clear" in response.data, (
            "Clear link must always be present on the profile page"
        )

    def test_clear_link_href_has_no_query_params(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        data = response.data.decode("utf-8")
        # The clear link href must be exactly /profile with no query string
        assert 'href="/profile"' in data, (
            "Clear link must point to /profile with no query params"
        )

    def test_clear_link_href_does_not_include_from_param(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        data = response.data.decode("utf-8")
        # Specifically the clear link's href must not embed filter params
        assert 'href="/profile?from=' not in data, (
            "Clear link must not include ?from= in its href"
        )


# ------------------------------------------------------------------ #
# 6. from after to — falls back to all-time                          #
# ------------------------------------------------------------------ #

class TestFromAfterTo:
    @pytest.fixture(autouse=True)
    def _seed(self, client, test_db):
        self.user_id = _insert_user(test_db)
        _insert_expenses(test_db, self.user_id, [
            (100.00, "Food",  "2026-04-01", "Lunch"),
            (200.00, "Bills", "2026-04-15", "Internet"),
        ])
        _login(client)
        # from is AFTER to — invalid range
        self.response = client.get("/profile?from=2026-04-30&to=2026-04-01")

    def test_returns_200_no_exception(self):
        assert self.response.status_code == 200, (
            "from > to must not raise an exception — must return 200"
        )

    def test_no_filter_label_shown(self):
        assert b"Filtered:" not in self.response.data, (
            "No filter label must appear when from is after to"
        )

    def test_all_time_data_is_shown(self):
        # Both expenses must be present: total = ₹300.00
        assert b"\xe2\x82\xb9300.00" in self.response.data, (
            "All-time data must be shown when from > to (fall back, not filter)"
        )


# ------------------------------------------------------------------ #
# 7. Only one param provided — falls back to all-time                #
# ------------------------------------------------------------------ #

class TestOnlyOneParamProvided:
    @pytest.fixture(autouse=True)
    def _seed(self, client, test_db):
        self.user_id = _insert_user(test_db)
        _insert_expenses(test_db, self.user_id, [
            (150.00, "Food",  "2026-03-01", "March lunch"),
            (250.00, "Bills", "2026-04-01", "April bill"),
        ])
        _login(client)

    def test_only_from_param_returns_200(self, client):
        response = client.get("/profile?from=2026-04-01")
        assert response.status_code == 200, (
            "Only 'from' param must not raise an error"
        )

    def test_only_from_param_no_filter_label(self, client):
        response = client.get("/profile?from=2026-04-01")
        assert b"Filtered:" not in response.data, (
            "No filter label when only 'from' is provided"
        )

    def test_only_from_param_shows_all_time_data(self, client):
        response = client.get("/profile?from=2026-04-01")
        # All-time total = ₹400.00
        assert b"\xe2\x82\xb9400.00" in response.data, (
            "All-time data must be returned when only 'from' is given"
        )

    def test_only_to_param_returns_200(self, client):
        response = client.get("/profile?to=2026-04-30")
        assert response.status_code == 200, (
            "Only 'to' param must not raise an error"
        )

    def test_only_to_param_no_filter_label(self, client):
        response = client.get("/profile?to=2026-04-30")
        assert b"Filtered:" not in response.data, (
            "No filter label when only 'to' is provided"
        )

    def test_only_to_param_shows_all_time_data(self, client):
        response = client.get("/profile?to=2026-04-30")
        # All-time total = ₹400.00
        assert b"\xe2\x82\xb9400.00" in response.data, (
            "All-time data must be returned when only 'to' is given"
        )


# ------------------------------------------------------------------ #
# 8. Filter range with no matching expenses                          #
# ------------------------------------------------------------------ #

class TestEmptyDateRange:
    @pytest.fixture(autouse=True)
    def _seed(self, client, test_db):
        self.user_id = _insert_user(test_db)
        # All expenses are in April; filter will target January (no matches)
        _insert_expenses(test_db, self.user_id, [
            (500.00, "Bills", "2026-04-10", "Electricity"),
        ])
        _login(client)
        self.response = client.get("/profile?from=2026-01-01&to=2026-01-31")

    def test_returns_200_no_exception(self):
        assert self.response.status_code == 200, (
            "Empty result set must not raise an exception"
        )

    def test_total_spent_is_zero(self):
        assert b"\xe2\x82\xb90.00" in self.response.data, (
            "Total spent must be ₹0.00 when no expenses match the range"
        )

    def test_transaction_count_is_zero(self):
        # The stats block must show 0 transactions
        assert b"0" in self.response.data, (
            "Transaction count must be 0 for an empty range"
        )

    def test_top_category_is_dash(self):
        assert "—".encode("utf-8") in self.response.data, (
            "Top category must be '—' when no expenses match the range"
        )

    def test_transaction_list_is_empty(self):
        # None of the seeded expense descriptions should appear
        assert b"Electricity" not in self.response.data, (
            "Out-of-range expense must not appear in the transaction list"
        )

    def test_category_breakdown_is_empty(self):
        # Bills category must not appear in breakdown
        assert b"breakdown-row" not in self.response.data or b"Bills" not in self.response.data, (
            "Category breakdown must be empty when no expenses match the range"
        )

    def test_filter_label_is_present(self):
        # The range IS valid (Jan 1 <= Jan 31), so the filter label should appear
        assert b"Filtered:" in self.response.data, (
            "Filter label must appear even when the valid range yields zero results"
        )

    def test_filter_label_contains_correct_dates(self):
        assert b"01 Jan 2026" in self.response.data, (
            "Filter label from-date must be formatted correctly"
        )
        assert b"31 Jan 2026" in self.response.data, (
            "Filter label to-date must be formatted correctly"
        )


# ------------------------------------------------------------------ #
# 9. Malformed / non-date strings in params                          #
# ------------------------------------------------------------------ #

class TestMalformedDateParams:
    @pytest.fixture(autouse=True)
    def _seed(self, client, test_db):
        self.user_id = _insert_user(test_db)
        _insert_expenses(test_db, self.user_id, [
            (75.00, "Food", "2026-04-10", "Salad"),
        ])
        _login(client)

    def test_malformed_from_does_not_crash(self, client):
        response = client.get("/profile?from=not-a-date&to=2026-04-30")
        assert response.status_code == 200, (
            "Malformed 'from' date must not cause a 500 error"
        )

    def test_malformed_to_does_not_crash(self, client):
        response = client.get("/profile?from=2026-04-01&to=oops")
        assert response.status_code == 200, (
            "Malformed 'to' date must not cause a 500 error"
        )

    def test_malformed_params_show_all_time_data(self, client):
        response = client.get("/profile?from=not-a-date&to=also-bad")
        assert response.status_code == 200
        assert b"\xe2\x82\xb975.00" in response.data, (
            "Malformed date params must fall back to all-time data"
        )

    def test_malformed_params_no_filter_label(self, client):
        response = client.get("/profile?from=not-a-date&to=also-bad")
        assert b"Filtered:" not in response.data, (
            "No filter label must appear for malformed date params"
        )


# ------------------------------------------------------------------ #
# 10. Data isolation between users                                    #
# ------------------------------------------------------------------ #

class TestUserDataIsolation:
    def test_filtered_data_belongs_only_to_logged_in_user(self, client, test_db):
        # Create two users; each has expenses in the same date range
        user_a_id = _insert_user(
            test_db, name="User A", email="usera@spendly.com"
        )
        user_b_id = _insert_user(
            test_db, name="User B", email="userb@spendly.com",
            created_at="2026-01-01 00:00:00"
        )
        _insert_expenses(test_db, user_a_id, [
            (500.00, "Bills", "2026-04-10", "User A expense"),
        ])
        _insert_expenses(test_db, user_b_id, [
            (999.00, "Food", "2026-04-10", "User B expense"),
        ])

        # Log in as User A
        _login(client, email="usera@spendly.com")
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")

        assert b"\xe2\x82\xb9500.00" in response.data, (
            "Logged-in user's own expenses must appear"
        )
        assert b"User B expense" not in response.data, (
            "Another user's expenses must never appear in the filtered view"
        )
        assert b"\xe2\x82\xb9999.00" not in response.data, (
            "Another user's total must not appear"
        )


# ------------------------------------------------------------------ #
# 11. Boundary dates — inclusive range                               #
# ------------------------------------------------------------------ #

class TestBoundaryDatesInclusive:
    """from and to are boundary dates; spec uses BETWEEN which is inclusive."""

    @pytest.fixture(autouse=True)
    def _seed(self, client, test_db):
        self.user_id = _insert_user(test_db)
        _insert_expenses(test_db, self.user_id, [
            (100.00, "Food", "2026-04-01", "On from-date"),   # boundary start
            (200.00, "Food", "2026-04-30", "On to-date"),     # boundary end
            (50.00,  "Food", "2026-04-15", "Mid-range"),      # inside
            (999.00, "Food", "2026-03-31", "Before range"),   # outside
            (888.00, "Food", "2026-05-01", "After range"),    # outside
        ])
        _login(client)
        self.response = client.get("/profile?from=2026-04-01&to=2026-04-30")

    def test_boundary_start_is_included(self):
        assert b"On from-date" in self.response.data, (
            "Expense on the from-date boundary must be included"
        )

    def test_boundary_end_is_included(self):
        assert b"On to-date" in self.response.data, (
            "Expense on the to-date boundary must be included"
        )

    def test_before_range_is_excluded(self):
        assert b"Before range" not in self.response.data, (
            "Expense before the from-date must be excluded"
        )

    def test_after_range_is_excluded(self):
        assert b"After range" not in self.response.data, (
            "Expense after the to-date must be excluded"
        )

    def test_total_is_sum_of_boundary_and_mid(self):
        # 100 + 200 + 50 = 350
        assert b"\xe2\x82\xb9350.00" in self.response.data, (
            "Total must include boundary dates and exclude dates outside range"
        )


# ------------------------------------------------------------------ #
# 12. Single-day range (from == to)                                  #
# ------------------------------------------------------------------ #

class TestSingleDayRange:
    def test_single_day_filter_returns_only_that_day(self, client, test_db):
        user_id = _insert_user(test_db)
        _insert_expenses(test_db, user_id, [
            (250.00, "Food",  "2026-04-15", "Target day"),
            (100.00, "Bills", "2026-04-14", "Day before"),
            (100.00, "Bills", "2026-04-16", "Day after"),
        ])
        _login(client)
        response = client.get("/profile?from=2026-04-15&to=2026-04-15")

        assert response.status_code == 200
        assert b"Target day" in response.data, (
            "Expense on the single target day must be included"
        )
        assert b"Day before" not in response.data
        assert b"Day after" not in response.data
        assert b"\xe2\x82\xb9250.00" in response.data, (
            "Total must be only the single-day expense"
        )

    def test_single_day_filter_label_shows_same_date_twice(self, client, test_db):
        _insert_user(test_db)
        _login(client)
        response = client.get("/profile?from=2026-04-15&to=2026-04-15")
        # label should be "Filtered: 15 Apr 2026 – 15 Apr 2026"
        data = response.data.decode("utf-8")
        assert data.count("15 Apr 2026") >= 2, (
            "Single-day filter label must show the same date on both sides of the en-dash"
        )
