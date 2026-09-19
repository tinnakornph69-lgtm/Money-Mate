"""MoneyMate financial reports."""

import os
from collections import defaultdict

from flask import session
from persistent_store import read_json


TITLE = "รายงาน"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(HERE, "money_data.json")


def load():
    data = read_json(FILE, [])
    return data if isinstance(data, list) else []


def safe_amount(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build(query=None):
    user = session.get("user")
    items = [
        item for item in load()
        if user and item.get("owner") == user
    ]

    months = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    categories = defaultdict(float)

    for item in items:
        transaction_type = item.get("type")
        if transaction_type not in ("income", "expense"):
            continue

        month = str(item.get("date", ""))[:7] or "ไม่ระบุ"
        amount = safe_amount(item.get("amount"))

        if transaction_type == "income":
            months[month]["income"] += amount
        elif transaction_type == "expense":
            months[month]["expense"] += amount
            category = item.get("category") or "อื่น ๆ"
            categories[category] += amount

    rows = []
    for month in sorted(months, reverse=True):
        values = months[month]
        rows.append({
            "month": month,
            "income": values["income"],
            "expense": values["expense"],
            "saving": values["income"] - values["expense"],
        })

    total_income = sum(row["income"] for row in rows)
    total_expense = sum(row["expense"] for row in rows)
    saving = total_income - total_expense
    rate = round(saving * 100 / total_income, 1) if total_income else 0

    return {
        "rows": rows,
        "cats": sorted(
            categories.items(),
            key=lambda pair: pair[1],
            reverse=True,
        ),
        "income": total_income,
        "expense": total_expense,
        "saving": saving,
        "rate": rate,
    }
