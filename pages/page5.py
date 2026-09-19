"""MoneyMate smart financial insights."""

import calendar
import os
from collections import defaultdict
from datetime import date, datetime

from flask import session

from persistent_store import read_json

TITLE = "Smart Output"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(HERE, "money_data.json")


def load():
    data = read_json(FILE, [])
    return data if isinstance(data, list) else []


def safe_amount(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def transaction_date(item):
    try:
        return datetime.strptime(str(item.get("date", ""))[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def build(query=None):
    user = session.get("user")
    today = date.today()
    month_key = today.strftime("%Y-%m")

    items = [item for item in load() if user and item.get("owner") == user]
    month_items = [
        item for item in items
        if str(item.get("date", ""))[:7] == month_key
    ]

    income = sum(
        safe_amount(item.get("amount"))
        for item in month_items
        if item.get("type") == "income"
    )
    expense = sum(
        safe_amount(item.get("amount"))
        for item in month_items
        if item.get("type") == "expense"
    )
    current_balance = income - expense

    categories = {}
    for item in month_items:
        if item.get("type") == "expense":
            category = item.get("category", "อื่น ๆ")
            categories[category] = categories.get(category, 0.0) + safe_amount(
                item.get("amount")
            )

    saving_rate = current_balance / income if income else 0
    score = round(max(0, min(100, 50 + saving_rate * 50))) if income else 50

    days_in_month = calendar.monthrange(today.year, today.month)[1]
    remaining_days = max(1, days_in_month - today.day + 1)
    daily_limit = max(0.0, current_balance / remaining_days)

    # เริ่มเฉลี่ยตั้งแต่วันที่มีรายจ่ายครั้งแรก ไม่รวมวันที่ก่อนหน้านั้น
    expense_dates = []
    for item in month_items:
        if item.get("type") != "expense":
            continue
        item_date = transaction_date(item)
        if item_date and item_date <= today:
            expense_dates.append(item_date)

    if expense > 0 and expense_dates:
        first_expense_date = min(expense_dates)
        active_days = max(1, (today - first_expense_date).days + 1)
        average_expense_per_active_day = expense / active_days
        future_days = max(0, days_in_month - today.day)
        projected_expense = expense + average_expense_per_active_day * future_days
    else:
        first_expense_date = None
        active_days = 0
        average_expense_per_active_day = 0.0
        projected_expense = expense

    forecast = income - projected_expense

    tips = []
    alerts = []
    if income == 0:
        tips.append("เริ่มบันทึกรายรับ เพื่อให้ระบบคำนวณสุขภาพการเงินได้แม่นขึ้น")
    elif expense > income:
        alerts.append("รายจ่ายเดือนนี้สูงกว่ารายรับที่บันทึกไว้")
    elif expense > income * 0.8:
        alerts.append("รายจ่ายใช้สัดส่วนสูงของรายรับ ควรติดตามหมวดที่ใช้มาก")
    else:
        tips.append("รายรับยังมากกว่ารายจ่าย ลองกันเงินส่วนหนึ่งไว้เป็นเงินออม")

    if categories:
        top_category = max(categories, key=categories.get)
        tips.append(
            f"หมวดที่ใช้มากที่สุดเดือนนี้คือ {top_category} "
            f"({categories[top_category]:,.2f} บาท)"
        )

    historical = defaultdict(list)
    for item in items:
        if item.get("type") == "expense":
            historical[item.get("category", "อื่น ๆ")].append(
                safe_amount(item.get("amount"))
            )

    for category, current_amount in categories.items():
        history = historical.get(category, [])
        if len(history) >= 3:
            average = sum(history) / len(history)
            if current_amount > average * 1.5:
                alerts.append(
                    f"หมวด {category} สูงกว่าค่าเฉลี่ยที่บันทึกไว้ประมาณ 50% ขึ้นไป"
                )

    return {
        "income": income,
        "expense": expense,
        "current_balance": current_balance,
        "score": score,
        "daily_limit": daily_limit,
        "forecast": forecast,
        "tips": tips,
        "alerts": alerts,
        "categories": sorted(
            categories.items(), key=lambda pair: pair[1], reverse=True
        )[:5],
        "month": month_key,
        "projected_expense": projected_expense,
        "first_expense_date": (
            first_expense_date.strftime("%d/%m/%Y") if first_expense_date else ""
        ),
        "active_days": active_days,
        "average_expense_per_active_day": average_expense_per_active_day,
    }

