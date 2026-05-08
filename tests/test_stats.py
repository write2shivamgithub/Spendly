import pytest
from database.queries import get_user_by_id, get_summary_stats


def test_get_user_by_id_returns_expected_keys(user_with_expenses):
    result = get_user_by_id(user_with_expenses)
    assert result is not None
    assert "name" in result
    assert "email" in result
    assert "member_since" in result


def test_get_user_by_id_member_since_format(user_with_expenses):
    result = get_user_by_id(user_with_expenses)
    assert result["member_since"] == "January 2026"


def test_get_user_by_id_not_found():
    result = get_user_by_id(9999)
    assert result is None


def test_get_summary_stats_with_expenses(user_with_expenses):
    result = get_summary_stats(user_with_expenses)
    assert result["total_spent"] == "₹580.00"
    assert result["transaction_count"] == 5
    assert result["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(user_no_expenses):
    result = get_summary_stats(user_no_expenses)
    assert result["total_spent"] == "₹0.00"
    assert result["transaction_count"] == 0
    assert result["top_category"] == "—"


def test_profile_route_with_valid_session(client):
    with client.session_transaction() as sess:
        from database.db import get_user_by_email as _get_user
        u = _get_user("demo@spendly.com")
        sess["user_id"] = u["id"]
        sess["user_name"] = u["name"]
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Demo User" in response.data
