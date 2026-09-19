"""MoneyMate dashboard."""
import json
import os
from flask import session
from datetime import date

TITLE = "Dashboard"

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(HERE, "money_data.json")


def load_transactions():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []

    except (OSError, json.JSONDecodeError):
        return []


def safe_amount(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def make_breakdown(categories):
    """
    แปลงข้อมูลหมวดหมู่เป็น
    ชื่อหมวด / จำนวนเงิน / เปอร์เซ็นต์
    """

    rows = sorted(
        categories.items(),
        key=lambda x: x[1],
        reverse=True
    )

    total = sum(value for _, value in rows)

    result = []

    cursor = 0

    for index, (name, value) in enumerate(rows):

        percentage = (
            value / total * 100
            if total > 0
            else 0
        )

        start = cursor
        end = cursor + percentage

        result.append({
            "name": name,
            "value": value,
            "percentage": percentage,
            "start": start,
            "end": end,
            "index": index
        })

        cursor = end

    # สร้าง gradient สำหรับวงกลม
    if result:

        colors = [
            "#7b1e2b",
            "#c85c5c",
            "#e0a458",
            "#5b8c85",
            "#5870a8",
            "#8b6f9d",
            "#6b8e5e",
            "#9a7b4f"
        ]

        stops = []

        for item in result:

            color = colors[
                item["index"] % len(colors)
            ]

            stops.append(
                f"{color} "
                f"{item['start']:.4f}% "
                f"{item['end']:.4f}%"
            )

        gradient = ", ".join(stops)

    else:

        gradient = "#e5e7eb 0% 100%"

    return result, total, gradient


def build(query=None):

    items = load_transactions()

    # เอาเฉพาะข้อมูลของผู้ใช้ที่ login
    user = session.get("user")

    items = [
        x for x in items
        if user and x.get("owner") == user
    ]

    today = date.today()

    month_key = today.strftime("%Y-%m")

    # ข้อมูลเฉพาะเดือนปัจจุบัน
    month_items = [
        x for x in items
        if str(x.get("date", "")).startswith(month_key)
    ]

    # =========================
    # รายรับ / รายจ่ายทั้งหมด
    # =========================

    income = sum(
        safe_amount(x.get("amount", 0))
        for x in items
        if x.get("type") == "income"
    )

    expense = sum(
        safe_amount(x.get("amount", 0))
        for x in items
        if x.get("type") == "expense"
    )

    # =========================
    # รายรับ / รายจ่ายเดือนนี้
    # =========================

    month_income = sum(
        safe_amount(x.get("amount", 0))
        for x in month_items
        if x.get("type") == "income"
    )

    month_expense = sum(
        safe_amount(x.get("amount", 0))
        for x in month_items
        if x.get("type") == "expense"
    )

    # =========================
    # แยกหมวดรายรับ / รายจ่าย
    # =========================

    income_categories = {}
    expense_categories = {}

    for x in month_items:

        category = (
            x.get("category")
            or "อื่น ๆ"
        )

        amount = safe_amount(
            x.get("amount", 0)
        )

        # รายรับ
        if x.get("type") == "income":

            income_categories[category] = (
                income_categories.get(category, 0)
                + amount
            )

        # รายจ่าย
        elif x.get("type") == "expense":

            expense_categories[category] = (
                expense_categories.get(category, 0)
                + amount
            )

    # =========================
    # สร้างข้อมูลกราฟ
    # =========================

    income_breakdown, income_total, income_pie_gradient = (
        make_breakdown(income_categories)
    )

    expense_breakdown, expense_total, expense_pie_gradient = (
        make_breakdown(expense_categories)
    )

    # หมวดที่ใช้เงินมากที่สุด
    top_categories = expense_breakdown[:5]

    # รายการล่าสุด
    recent = sorted(
        items,
        key=lambda x: (
            str(x.get("date", "")),
            str(x.get("created_at", "")),
        ),
        reverse=True
    )[:7]

    return {

        # ยอดรวม
        "income": income,
        "expense": expense,
        "balance": income - expense,

        # เดือนนี้
        "month_income": month_income,
        "month_expense": month_expense,
        "month_balance": month_income - month_expense,

        "month": today.strftime("%B %Y"),

        # รายรับแยกหมวด
        "income_breakdown": income_breakdown,
        "income_total": income_total,
        "income_pie_gradient": income_pie_gradient,

        # รายจ่ายแยกหมวด
        "expense_breakdown": expense_breakdown,
        "expense_total": expense_total,
        "expense_pie_gradient": expense_pie_gradient,

        # หมวดที่ใช้มาก
        "top_categories": top_categories,

        # รายการล่าสุด
        "recent": recent,

        # จำนวนรายการ
        "count": len(items)
    }
