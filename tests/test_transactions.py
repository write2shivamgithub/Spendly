import pytest
from database.queries import get_recent_transactions


def test_returns_non_empty_list(user_with_expenses):
    result = get_recent_transactions(user_with_expenses)
    assert isinstance(result, list)
    assert len(result) > 0


def test_first_item_is_newest(user_with_expenses):
    result = get_recent_transactions(user_with_expenses)
    assert result[0]["date"] == "10 Apr 2026"


def test_last_item_is_oldest(user_with_expenses):
    result = get_recent_transactions(user_with_expenses)
    assert result[-1]["date"] == "28 Mar 2026"


def test_all_items_have_required_keys(user_with_expenses):
    result = get_recent_transactions(user_with_expenses)
    for item in result:
        assert "date" in item
        assert "description" in item
        assert "category" in item
        assert "amount" in item


def test_all_amounts_start_with_rupee_symbol(user_with_expenses):
    result = get_recent_transactions(user_with_expenses)
    for item in result:
        assert item["amount"].startswith("₹")


def test_no_expenses_returns_empty_list(user_no_expenses):
    result = get_recent_transactions(user_no_expenses)
    assert result == []


def test_profile_unauthenticated_redirects(client):
    response = client.get("/profile")
    assert response.status_code == 302
