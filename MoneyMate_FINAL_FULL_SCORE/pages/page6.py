"""MoneyMate flexible budget planner."""
import os
from datetime import date, timedelta
from flask import has_request_context, session
from persistent_store import read_json, write_json

TITLE = "งบประมาณ"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BFILE = os.path.join(HERE, "budget_data.json")
TFILE = os.path.join(HERE, "money_data.json")
CATS = ["อาหาร","เดินทาง","ช้อปปิ้ง","บิล/ค่าใช้จ่าย","การศึกษา","สุขภาพ","ความบันเทิง","เงินเดือน","งานเสริม","อื่น ๆ"]
PERIODS = {
    "daily": "รายวัน",
    "weekly": "รายสัปดาห์",
    "monthly": "รายเดือน",
    "yearly": "รายปี",
}

def read(path, default):
    return read_json(path, default)

def save(data):
    write_json(BFILE, data)

def current_period(period, d=None):
    d = d or date.today()
    if period == "daily":
        return d.isoformat()
    if period == "weekly":
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if period == "yearly":
        return str(d.year)
    return d.strftime("%Y-%m")

def period_of_transaction(value, period):
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        return ""
    return current_period(period, d)

def user_budget(data, user):
    if not isinstance(data, dict):
        data = {}
    users = data.setdefault("users", {})
    bucket = users.setdefault(user or "__guest__", {})
    if not isinstance(bucket, dict):
        bucket = {}
        users[user or "__guest__"] = bucket

    # New structure: budgets[period][period_key], categories[period][period_key][category]
    bucket.setdefault("budgets", {})
    bucket.setdefault("categories", {})

    # Migrate the old monthly/category structure once.
    old_monthly = bucket.get("monthly")
    old_categories = bucket.get("categories")
    if isinstance(old_monthly, dict) and old_monthly:
        bucket["budgets"].setdefault("monthly", {}).update(old_monthly)
        bucket.pop("monthly", None)
    if isinstance(old_categories, dict) and old_categories:
        # old: categories[month][category]
        # new: categories[period][period_key][category]
        old_month_keys = [
            key for key in old_categories
            if key not in PERIODS
        ]

        if old_month_keys:
            migrated = {
                key: value
                for key, value in old_categories.items()
                if key in PERIODS and isinstance(value, dict)
            }
            monthly_categories = migrated.setdefault("monthly", {})

            for key in old_month_keys:
                value = old_categories.get(key)
                if isinstance(value, dict):
                    monthly_categories.setdefault(key, {}).update(value)

            bucket["categories"] = migrated
    return data, bucket

def categories_for(items):
    extras = sorted({str(x.get("category","")).strip() for x in items
                     if str(x.get("category","")).strip() and x.get("category") not in CATS})
    return CATS[:-1] + extras + ["อื่น ๆ"]

def build(query=None):
    query = query or {}
    user = session.get("user")
    data = read(BFILE, {"users": {}})
    data, budget = user_budget(data, user)
    items = read(TFILE, [])
    items = [x for x in items if user and x.get("owner") == user]

    period = query.get("period", "monthly")
    if period not in PERIODS:
        period = "monthly"
    key = current_period(period)
    exp = sum(float(x.get("amount", 0)) for x in items
              if x.get("type") == "expense" and period_of_transaction(x.get("date",""), period) == key)

    cats = categories_for(items)
    cat_spend = {
        c: sum(float(x.get("amount", 0)) for x in items
               if x.get("type") == "expense"
               and period_of_transaction(x.get("date",""), period) == key
               and x.get("category") == c)
        for c in cats
    }
    monthly = float(budget.get("budgets", {}).get(period, {}).get(key, 0))
    category_bucket = budget.get("categories", {}).get(period, {}).get(key, {})
    if not isinstance(category_bucket, dict):
        category_bucket = {}

    # แสดงทั้งหมวดที่มีธุรกรรมและหมวดที่ผู้ใช้เคยตั้งงบ
    cats = sorted(set(cats) | set(category_bucket.keys()))
    rows = []
    for c in cats:
        b = float(category_bucket.get(c, 0) or 0)
        spent = cat_spend[c]
        pct = min(100, round(spent * 100 / b)) if b else 0
        rows.append({"category": c, "budget": b, "spent": spent, "pct": pct})

    return {
        "period": period,
        "period_label": PERIODS[period],
        "period_key": key,
        "periods": PERIODS,
        "monthly": monthly,
        "expense": exp,
        "remaining": max(0.0, monthly - exp),
        "rows": rows,
        "categories": cats,
    }


def _selected_values(form, name):
    """อ่านค่าหลายค่าจาก checkbox ได้ทั้ง MultiDict และ dict ปกติ"""
    if hasattr(form, "getlist"):
        return [str(v).strip() for v in form.getlist(name) if str(v).strip()]
    value = form.get(name, [])
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []

def handle(form):
    # รองรับการตรวจ handle({}) จาก check_project.py นอก request context
    if not has_request_context():
        return "กรุณาเข้าสู่ระบบก่อน"

    user = session.get("user")
    if not user:
        return "กรุณาเข้าสู่ระบบก่อน"

    action = form.get("action", "")
    period = form.get("period", "monthly")
    if period not in PERIODS:
        period = "monthly"
    data = read(BFILE, {"users": {}})
    data, budget = user_budget(data, user)
    key = current_period(period)

    if action == "bulk_delete_categories":
        selected = set(_selected_values(form, "selected_categories"))
        if not selected:
            return "กรุณาเลือกงบหมวดที่ต้องการลบ"
        categories = budget.setdefault("categories", {}).setdefault(period, {}).setdefault(key, {})
        deleted = 0
        for category in list(categories):
            if category in selected:
                del categories[category]
                deleted += 1
        if not deleted:
            return "ไม่พบงบหมวดที่ต้องการลบ"
        save(data)
        return f"ลบงบหมวด {deleted} รายการเรียบร้อยแล้ว"

    try:
        value = float(form.get("amount", 0))
    except (ValueError, TypeError):
        return "จำนวนเงินไม่ถูกต้อง"
    if value < 0:
        return "จำนวนเงินไม่ถูกต้อง"

    if action == "budget":
        budget.setdefault("budgets", {}).setdefault(period, {})[key] = value
        save(data)
        return f"บันทึกงบ{PERIODS[period]}แล้ว"

    if action == "category":
        category = form.get("category", "").strip()
        custom = form.get("custom_category", "").strip()
        if category == "อื่น ๆ" and custom:
            category = custom[:60]
        if not category:
            return "กรุณาเลือกหรือพิมพ์หมวดหมู่"
        budget.setdefault("categories", {}).setdefault(period, {}).setdefault(key, {})[category] = value
        save(data)
        return f"บันทึกงบหมวดหมู่แบบ{PERIODS[period]}แล้ว"

    return ""
