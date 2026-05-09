from database.db import get_db
from datetime import datetime


def get_user_by_id(user_id):
    db = get_db()
    try:
        row = db.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        name, email, created_at = row["name"], row["email"], row["created_at"]
        dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        member_since = dt.strftime("%B %Y")
        return {"name": name, "email": email, "member_since": member_since}
    finally:
        db.close()


def _date_filter_clause(user_id, date_from, date_to):
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (user_id, date_from, date_to)
    return "", (user_id,)


def get_summary_stats(user_id, date_from=None, date_to=None):
    date_filter, params = _date_filter_clause(user_id, date_from, date_to)
    db = get_db()
    try:
        total = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?" + date_filter,
            params,
        ).fetchone()[0]
        transaction_count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?" + date_filter,
            params,
        ).fetchone()[0]
        top_row = db.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + date_filter +
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            params,
        ).fetchone()
        top_category = top_row[0] if top_row else "—"
    finally:
        db.close()
    return {
        "total_spent": f"₹{total:,.2f}",
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    date_filter, params = _date_filter_clause(user_id, date_from, date_to)
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT date, description, category, amount FROM expenses WHERE user_id = ?" +
            date_filter + " ORDER BY date DESC LIMIT ?",
            params + (limit,),
        )
        rows = cursor.fetchall()
    finally:
        db.close()

    result = []
    for row in rows:
        formatted_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y")
        result.append({
            "date": formatted_date,
            "description": row["description"],
            "category": row["category"],
            "amount": f"₹{row['amount']:,.2f}",
        })
    return result


def get_category_breakdown(user_id, date_from=None, date_to=None):
    date_filter, params = _date_filter_clause(user_id, date_from, date_to)
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ?" +
            date_filter + " GROUP BY category ORDER BY total DESC",
            params,
        )
        rows = cursor.fetchall()
    finally:
        db.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)

    result = []
    for row in rows:
        percent = round(row["total"] / grand_total * 100)
        result.append({
            "category": row["category"],
            "percent": percent,
            "total": f"₹{row['total']:,.2f}",
        })

    remainder = 100 - sum(item["percent"] for item in result)
    result[0]["percent"] += remainder

    return result