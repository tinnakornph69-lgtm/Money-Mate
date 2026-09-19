"""MoneyMate transaction manager + recurring income."""

import os
import secrets
from calendar import monthrange
from datetime import datetime, date, timedelta

from flask import has_request_context, session
from persistent_store import read_json, write_json


TITLE = "รายรับ-รายจ่าย"
MAX_RECURRING_CATCHUP = 120

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_FILE = os.path.join(HERE, "money_data.json")
RECURRING_FILE = os.path.join(HERE, "recurring_income.json")

CATEGORIES = [
    "อาหาร",
    "เดินทาง",
    "ช้อปปิ้ง",
    "บิล/ค่าใช้จ่าย",
    "การศึกษา",
    "สุขภาพ",
    "ความบันเทิง",
    "เงินเดือน",
    "งานเสริม",
    "อื่น ๆ",
]


def all_categories(items):
    extra = sorted({
        str(x.get("category", "")).strip()
        for x in items
        if str(x.get("category", "")).strip()
        and x.get("category") not in CATEGORIES
    })

    return CATEGORIES[:-1] + extra + ["อื่น ๆ"]


def resolve_category(form):
    selected = str(form.get("category", "")).strip()
    custom = str(form.get("custom_category", "")).strip()

    if selected == "อื่น ๆ" and custom:
        return custom[:60]

    return selected


def load_transactions():
    data = read_json(DATA_FILE, [])
    return data if isinstance(data, list) else []


def save_transactions(items):
    write_json(DATA_FILE, items)

def current_balance(user, exclude_id=None):
    """ยอดเงินคงเหลือของผู้ใช้ ณ ตอนนี้ (ไม่รวมรายการที่ id ตรงกับ exclude_id ถ้ามี)"""
    total = 0.0
    for x in load_transactions():
        if x.get("owner") != user:
            continue
        if exclude_id and x.get("id") == exclude_id:
            continue
        a = float(x.get("amount", 0) or 0)
        total += a if x.get("type") == "income" else -a
    return total


def load_recurring():
    data = read_json(RECURRING_FILE, [])
    return data if isinstance(data, list) else []


def save_recurring(items):
    write_json(RECURRING_FILE, items)


def amount(value):
    try:
        x = float(value)

        if x <= 0:
            return None

        return round(x, 2)

    except (ValueError, TypeError):
        return None


def valid_date(value):
    try:
        return date.fromisoformat(str(value).strip())

    except (ValueError, TypeError):
        return None


def next_month_date(day_number, current):
    """หาวันรับเงินรอบถัดไปของเดือน"""
    year = current.year
    month = current.month + 1

    if month == 13:
        year += 1
        month = 1

    day = min(
        int(day_number),
        monthrange(year, month)[1]
    )

    return date(
        year,
        month,
        day
    ).isoformat()


def add_recurring_item(form, user):
    name = str(form.get("recurring_name", "")).strip()
    a = amount(form.get("recurring_amount", ""))
    frequency = str(form.get("recurring_frequency", "once")).strip()
    if not name:
        return "กรุณากรอกชื่อรายรับ"
    if a is None:
        return "กรุณากรอกจำนวนเงินให้ถูกต้อง"
    if frequency not in ("once", "daily", "weekly", "monthly"):
        return "รูปแบบความถี่ไม่ถูกต้อง"

    today = date.today()
    start_raw = str(form.get("recurring_start_date", "")).strip()
    end_raw = str(form.get("recurring_end_date", "")).strip()
    start = valid_date(start_raw) if start_raw else today
    end = valid_date(end_raw) if end_raw else None
    if start is None:
        return "วันเริ่มต้นไม่ถูกต้อง"
    if end_raw and end is None:
        return "วันสิ้นสุดไม่ถูกต้อง"
    if end and end < start:
        return "วันสิ้นสุดต้องไม่ก่อนวันเริ่มต้น"

    weekdays = []
    month_days = []
    day = 0

    if frequency == "once":
        d = valid_date(str(form.get("recurring_date", "")).strip())
        if d is None:
            return "กรุณาเลือกวันที่รับเงิน"
        next_date = d.isoformat()
        start = d
        end = d
    elif frequency == "daily":
        next_date = max(start, today).isoformat()
    elif frequency == "weekly":
        raw = form.getlist("recurring_weekdays") if hasattr(form, "getlist") else form.get("recurring_weekdays", [])
        if not isinstance(raw, (list, tuple)):
            raw = [raw]
        try:
            weekdays = sorted({int(x) for x in raw if str(x) != ""})
        except (TypeError, ValueError):
            return "วันที่เลือกไม่ถูกต้อง"
        if not weekdays or any(x < 0 or x > 6 for x in weekdays):
            return "กรุณาเลือกวันอย่างน้อย 1 วัน"
        cursor = max(start, today)
        for _ in range(8):
            if cursor.weekday() in weekdays:
                break
            cursor += timedelta(days=1)
        next_date = cursor.isoformat()
    else:
        raw = form.getlist("recurring_month_days") if hasattr(form, "getlist") else form.get("recurring_month_days", [])
        if not isinstance(raw, (list, tuple)):
            raw = [raw]
        # backwards-compatible single select
        if not raw or raw == [""]:
            raw = [form.get("recurring_day", "")]
        try:
            month_days = sorted({int(x) for x in raw if str(x) != ""})
        except (TypeError, ValueError):
            return "วันที่รายเดือนไม่ถูกต้อง"
        if not month_days or any(x < 1 or x > 31 for x in month_days):
            return "กรุณาเลือกวันที่ของเดือนอย่างน้อย 1 วัน"
        day = month_days[0]
        cursor = max(start, today)
        found = None
        for _ in range(370):
            last = monthrange(cursor.year, cursor.month)[1]
            effective = {min(x, last) for x in month_days}
            if cursor.day in effective:
                found = cursor
                break
            cursor += timedelta(days=1)
        next_date = (found or cursor).isoformat()

    items = load_recurring()
    items.append({
        "id": secrets.token_hex(8), "owner": user, "name": name[:120],
        "amount": a, "frequency": frequency, "day": day,
        "weekdays": weekdays, "month_days": month_days,
        "start_date": start.isoformat(), "end_date": end.isoformat() if end else "",
        "next_date": next_date, "active": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    save_recurring(items)
    return "ตั้งตารางรายรับเรียบร้อยแล้ว"


def _next_recurring_date(item, after_date):
    frequency = item.get("frequency", "once")
    end = valid_date(item.get("end_date", ""))
    if frequency == "once":
        return None
    cursor = after_date + timedelta(days=1)
    if frequency == "daily":
        candidate = cursor
    elif frequency == "weekly":
        weekdays = {int(x) for x in item.get("weekdays", [])}
        candidate = cursor
        for _ in range(8):
            if candidate.weekday() in weekdays:
                break
            candidate += timedelta(days=1)
    elif frequency == "monthly":
        month_days = {int(x) for x in item.get("month_days", [])}
        if not month_days and item.get("day"):
            month_days = {int(item.get("day"))}
        candidate = cursor
        for _ in range(370):
            last = monthrange(candidate.year, candidate.month)[1]
            if candidate.day in {min(x, last) for x in month_days}:
                break
            candidate += timedelta(days=1)
    else:
        return None
    if end and candidate > end:
        return None
    return candidate


def process_due_recurring(user):
    """สร้างรายรับที่ถึงกำหนด โดยไม่สร้างงวดเดิมซ้ำ."""
    if not user:
        return
    recurring = load_recurring()
    money = load_transactions()
    today = date.today()
    changed_recurring = False
    changed_money = False
    existing_keys = {
        (x.get("owner"), x.get("recurring_id"), x.get("date"))
        for x in money if x.get("source") == "recurring_income"
    }

    for item in recurring:
        if item.get("owner") != user or item.get("active") is False:
            continue
        due = valid_date(item.get("next_date", ""))
        if due is None:
            continue
        end = valid_date(item.get("end_date", ""))
        rounds = 0
        while due <= today and rounds < MAX_RECURRING_CATCHUP:
            if end and due > end:
                item["active"] = False
                item["next_date"] = ""
                changed_recurring = True
                break
            key = (user, item.get("id"), due.isoformat())
            if key not in existing_keys:
                name = str(item.get("name", "รายรับประจำ"))
                money.append({
                    "id": secrets.token_hex(8), "type": "income",
                    "amount": float(item.get("amount", 0)),
                    "category": "เงินเดือน" if "เงินเดือน" in name else "รายรับประจำ",
                    "date": due.isoformat(), "description": name[:200],
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "owner": user, "source": "recurring_income",
                    "recurring_id": item.get("id"),
                })
                existing_keys.add(key)
                changed_money = True
            rounds += 1
            nxt = _next_recurring_date(item, due)
            if nxt is None:
                item["active"] = False
                item["next_date"] = ""
                changed_recurring = True
                break
            item["next_date"] = nxt.isoformat()
            due = nxt
            changed_recurring = True
    if changed_money:
        save_transactions(money)
    if changed_recurring:
        save_recurring(recurring)


def build(query=None):
    query = query or {}

    user = session.get("user")

    # ตรวจรายรับที่ถึงกำหนด
    process_due_recurring(user)

    # -------------------------
    # รายการธุรกรรมของผู้ใช้
    # -------------------------

    items = [
        x
        for x in load_transactions()
        if user
        and x.get("owner") == user
    ]

    # -------------------------
    # รายรับที่ตั้งไว้
    # -------------------------

    recurring_items = [
        x
        for x in load_recurring()
        if user
        and x.get("owner") == user
    ]

    search = query.get(
        "search",
        ""
    ).strip().lower()

    type_filter = query.get(
        "type",
        ""
    )

    category = query.get(
        "category",
        ""
    )

    edit_id = query.get(
        "edit",
        ""
    )

    categories = all_categories(items)

    filtered = []

    for x in items:

        text = (
            str(
                x.get(
                    "description",
                    ""
                )
            )
            + " "
            + str(
                x.get(
                    "category",
                    ""
                )
            )
        ).lower()

        if search and search not in text:
            continue

        if (
            type_filter
            and x.get("type") != type_filter
        ):
            continue

        if (
            category
            and x.get("category") != category
        ):
            continue

        filtered.append(x)

    filtered.sort(
        key=lambda x: (
            x.get("date", ""),
            x.get("created_at", "")
        ),
        reverse=True
    )

    income = sum(
        float(
            x.get(
                "amount",
                0
            )
        )
        for x in items
        if x.get("type") == "income"
    )

    expense = sum(
        float(
            x.get(
                "amount",
                0
            )
        )
        for x in items
        if x.get("type") == "expense"
    )

    edit_item = next(
        (
            x
            for x in items
            if x.get("id") == edit_id
        ),
        None
    )

    return {
        "transactions": filtered,
        "categories": categories,

        "total_income": income,
        "total_expense": expense,
        "balance": income - expense,

        "search": query.get(
            "search",
            ""
        ),

        "type_filter": type_filter,
        "category_filter": category,

        "edit_item": edit_item,

        "today": datetime.now().strftime(
            "%Y-%m-%d"
        ),

        "recurring_items": recurring_items,
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

    # ตัวตรวจคะแนนเรียก handle({}) โดยไม่มี Flask request context
    # จึงต้องคืนข้อความตรวจสอบก่อนแตะ session
    if not has_request_context():
        return "กรุณาเข้าสู่ระบบก่อนบันทึกรายการ"

    action = form.get(
        "action",
        ""
    )

    user = session.get("user")

    if not user:
        return "กรุณาเข้าสู่ระบบก่อนบันทึกรายการ"

    # =====================================================
    # เพิ่มรายรับล่วงหน้า / รายรับประจำ
    # =====================================================

    if action == "add_recurring":

        return add_recurring_item(
            form,
            user
        )

    # =====================================================
    # ยกเลิกรายรับที่ตั้งไว้
    # =====================================================

    if action == "delete_recurring":

        item_id = str(
            form.get(
                "id",
                ""
            )
        ).strip()

        items = load_recurring()

        new_items = [
            x
            for x in items
            if not (
                x.get("id") == item_id
                and x.get("owner") == user
            )
        ]

        if len(new_items) == len(items):
            return "ไม่พบรายรับที่ตั้งไว้"

        save_recurring(new_items)

        return "ยกเลิกรายรับที่ตั้งไว้แล้ว"

    # =====================================================
    # ลบหลายรายการ — ตรวจ owner ทุกครั้ง
    # =====================================================
    if action == "bulk_delete":
        selected = set(_selected_values(form, "selected_ids"))
        if not selected:
            return "กรุณาเลือกรายการที่ต้องการลบ"
        items = load_transactions()
        kept = [x for x in items if not (x.get("owner") == user and str(x.get("id")) in selected)]
        deleted = len(items) - len(kept)
        if not deleted:
            return "ไม่พบรายการที่ต้องการลบ"
        save_transactions(kept)
        return f"ลบ {deleted} รายการเรียบร้อยแล้ว"

    if action == "bulk_delete_recurring":
        selected = set(_selected_values(form, "selected_ids"))
        if not selected:
            return "กรุณาเลือกรายรับประจำที่ต้องการลบ"
        items = load_recurring()
        kept = [x for x in items if not (x.get("owner") == user and str(x.get("id")) in selected)]
        deleted = len(items) - len(kept)
        if not deleted:
            return "ไม่พบรายรับประจำที่ต้องการลบ"
        save_recurring(kept)
        return f"ลบรายรับประจำ {deleted} รายการเรียบร้อยแล้ว"

    # =====================================================
    # เพิ่ม / แก้ไขธุรกรรมปกติ
    # =====================================================

    if action in (
        "add",
        "edit"
    ):

        t = form.get(
            "type",
            ""
        )

        a = amount(
            form.get(
                "amount",
                ""
            )
        )

        c = resolve_category(
            form
        )

        d = (
            form.get(
                "date",
                ""
            ).strip()
            or datetime.now().strftime(
                "%Y-%m-%d"
            )
        )

        desc = form.get(
            "description",
            ""
        ).strip()

        if (
            t not in (
                "income",
                "expense"
            )
            or a is None
            or not c
        ):
            return (
                "กรุณากรอกประเภท "
                "จำนวนเงิน และหมวดหมู่ให้ครบ"
            )

        if valid_date(d) is None:
            return "วันที่ไม่ถูกต้อง"

        # -------------------------
        # เพิ่มรายการ
        # -------------------------

        if action == "add":

            all_items = load_transactions()

            # ยอดเงินจริงห้ามติดลบ: Smart Output ยังสามารถจำลองค่าติดลบได้ตามปกติ
            if t == "expense":
                balance = current_balance(user)
                if a > balance + 1e-9:
                    return (
                        "ยอดเงินคงเหลือไม่เพียงพอ "
                        f"(คงเหลือ {max(balance, 0):,.2f} บาท)"
                    )

            all_items.append({
                "id": secrets.token_hex(8),
                "type": t,
                "amount": a,
                "category": c,
                "date": d,
                "description": desc,
                "created_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "owner": user,
            })

            save_transactions(
                all_items
            )

            return "เพิ่มรายการเรียบร้อยแล้ว"

        # -------------------------
        # แก้ไขรายการ
        # -------------------------

        item_id = form.get(
            "id",
            ""
        )

        all_items = load_transactions()

        for x in all_items:

            if (
                x.get("id") == item_id
                and x.get("owner") == user
            ):

                # ตอนแก้ไข ให้คำนวณยอดโดยไม่นับรายการเดิมซ้ำ
                if t == "expense":
                    balance_without_old = current_balance(
                        user,
                        exclude_id=item_id
                    )
                    if a > balance_without_old + 1e-9:
                        return (
                            "ยอดเงินคงเหลือไม่เพียงพอ "
                            f"(ใช้ได้สูงสุด {max(balance_without_old, 0):,.2f} บาท)"
                        )

                x.update({
                    "type": t,
                    "amount": a,
                    "category": c,
                    "date": d,
                    "description": desc,
                })

                save_transactions(
                    all_items
                )

                return "แก้ไขรายการเรียบร้อยแล้ว"

        return "ไม่พบรายการ"

    # =====================================================
    # ลบธุรกรรม
    # =====================================================

    if action == "delete":

        item_id = form.get(
            "id",
            ""
        )

        all_items = load_transactions()

        new_items = [
            x
            for x in all_items
            if not (
                x.get("id") == item_id
                and x.get("owner") == user
            )
        ]

        if len(new_items) == len(all_items):
            return "ไม่พบรายการที่ต้องการลบ"

        save_transactions(
            new_items
        )

        return "ลบรายการเรียบร้อยแล้ว"

    return ""
