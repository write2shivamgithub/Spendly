from database.queries import get_category_breakdown


def test_returns_nonempty_list(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    assert isinstance(result, list)
    assert len(result) > 0


def test_first_item_is_bills(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    assert result[0]["category"] == "Bills"


def test_all_items_have_required_keys(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    for item in result:
        assert "category" in item
        assert "percent" in item
        assert "total" in item


def test_all_totals_start_with_rupee(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    for item in result:
        assert item["total"].startswith("₹")


def test_percent_values_are_integers(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    for item in result:
        assert isinstance(item["percent"], int)


def test_percents_sum_to_100(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    assert sum(item["percent"] for item in result) == 100


def test_ordered_descending_by_amount(user_with_expenses):
    result = get_category_breakdown(user_with_expenses)
    categories = [item["category"] for item in result]
    assert categories == ["Bills", "Food", "Transport", "Entertainment"]


def test_no_expenses_returns_empty_list(user_no_expenses):
    result = get_category_breakdown(user_no_expenses)
    assert result == []
