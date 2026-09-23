"""MoneyMate six-month financial analysis."""

import os
import math
from collections import defaultdict
from datetime import date

from flask import session
from persistent_store import read_json


TITLE = "วิเคราะห์การเงิน"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(HERE, "money_data.json")


def load():
    data = read_json(FILE, [])
    return data if isinstance(data, list) else []


def safe_amount(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value > 0 else 0.0


def build(query=None):
    user = session.get("user")
    items = [
        item for item in load()
        if user and item.get("owner") == user
    ]

    monthly = defaultdict(lambda: {"income": 0.0, "expense": 0.0})

    for item in items:
        month = str(item.get("date", ""))[:7]
        if len(month) != 7:
            continue

        amount = safe_amount(item.get("amount"))

        if item.get("type") == "income":
            monthly[month]["income"] += amount
        elif item.get("type") == "expense":
            monthly[month]["expense"] += amount

    months = sorted(monthly)[-6:]
    selected_months = set(months)
    categories = defaultdict(float)

    for item in items:
        month = str(item.get("date", ""))[:7]
        if month in selected_months and item.get("type") == "expense":
            category = item.get("category") or "อื่น ๆ"
            categories[category] += safe_amount(item.get("amount"))

    rows = []
    for month in months:
        income = monthly[month]["income"]
        expense = monthly[month]["expense"]
        rows.append({
            "month": month,
            "income": income,
            "expense": expense,
            "balance": max(0.0, income - expense),
        })

    top = sorted(categories.items(), key=lambda pair: pair[1], reverse=True)
    total_income = sum(row["income"] for row in rows)
    total_expense = sum(row["expense"] for row in rows)
    max_category = max((value for _, value in top), default=1)
    max_month = max(
        (max(row["income"], row["expense"]) for row in rows),
        default=1,
    )

    category_rows = [
        {
            "name": name,
            "amount": amount,
            "pct": round(amount * 100 / total_expense, 1)
            if total_expense else 0,
            "bar": round(amount * 100 / max_category)
            if max_category else 0,
        }
        for name, amount in top
    ]

    saving_rate = (
        round(max(0.0, min(100.0, (total_income - total_expense) * 100 / total_income)), 1)
        if total_income else 0
    )

    return {
        "rows": rows,
        "categories": category_rows,
        "max_month": max_month,
        "total_expense": total_expense,
        "total_income": total_income,
        "saving_rate": saving_rate,
        "now": date.today().strftime("%Y-%m"),
    }
