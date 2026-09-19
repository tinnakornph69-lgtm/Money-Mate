"""MoneyMate transaction manager + recurring income."""

import os
import secrets
from calendar import monthrange
from datetime import datetime, date

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
    name = str(
        form.get("recurring_name", "")
    ).strip()

    a = amount(
        form.get("recurring_amount", "")
    )

    frequency = str(
        form.get("recurring_frequency", "once")
    ).strip()

    if not name:
        return "กรุณากรอกชื่อรายรับประจำ"

    if a is None:
        return "กรุณากรอกจำนวนเงินรายรับประจำให้ถูกต้อง"

    if frequency not in ("once", "monthly"):
        return "รูปแบบความถี่ไม่ถูกต้อง"

    # -------------------------
    # รับครั้งเดียว
    # -------------------------

    if frequency == "once":

        raw_date = str(
            form.get("recurring_date", "")
        ).strip()

        d = valid_date(raw_date)

        if d is None:
            return "กรุณาเลือกวันที่รายรับ"

        next_date = d.isoformat()
        day = d.day

    # -------------------------
    # รับทุกเดือน
    # -------------------------

    else:

        try:
            day = int(
                form.get("recurring_day", "")
            )

        except (ValueError, TypeError):
            return "กรุณาเลือกวันที่รับรายเดือน"

        if not 1 <= day <= 31:
            return "วันที่รายเดือนต้องอยู่ระหว่าง 1-31"

        today = date.today()

        day = min(
            day,
            monthrange(
                today.year,
                today.month
            )[1]
        )

        candidate = date(
            today.year,
            today.month,
            day
        )

        if candidate < today:
            next_date = next_month_date(
                day,
                today
            )
        else:
            next_date = candidate.isoformat()

    items = load_recurring()

    items.append({
        "id": secrets.token_hex(8),
        "owner": user,
        "name": name[:120],
        "amount": a,
        "frequency": frequency,
        "day": day,
        "next_date": next_date,
        "active": True,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    })

    save_recurring(items)

    return "ตั้งรายรับล่วงหน้าเรียบร้อยแล้ว"


def process_due_recurring(user):
    """
    ตรวจรายรับที่ถึงกำหนดแล้ว
    และเพิ่มเข้า money_data.json อัตโนมัติ
    """

    if not user:
        return

    recurring = load_recurring()
    money = load_transactions()

    today = date.today()

    changed_recurring = False
    changed_money = False

    # เก็บรายการที่เคยสร้างแล้ว
    # เพื่อป้องกันการเพิ่มเงินซ้ำ
    existing_keys = {
        (
            x.get("owner"),
            x.get("recurring_id"),
            x.get("date"),
        )
        for x in money
        if x.get("source") == "recurring_income"
    }

    for item in recurring:

        if item.get("owner") != user:
            continue

        if item.get("active") is False:
            continue

        due = valid_date(
            item.get("next_date", "")
        )

        if due is None:
            continue

        if due > today:
            continue

        frequency = item.get(
            "frequency",
            "once"
        )

        if frequency not in ("once", "monthly"):
            item["active"] = False
            changed_recurring = True
            continue

        # -------------------------
        # เพิ่มรายการที่ถึงกำหนด
        # -------------------------

        processed_rounds = 0

        while (
            due is not None
            and due <= today
            and processed_rounds < MAX_RECURRING_CATCHUP
        ):

            key = (
                user,
                item.get("id"),
                due.isoformat(),
            )

            if key not in existing_keys:

                name = str(
                    item.get(
                        "name",
                        "รายรับประจำ"
                    )
                )

                category = (
                    "เงินเดือน"
                    if "เงินเดือน" in name
                    else "รายรับประจำ"
                )

                money.append({
                    "id": secrets.token_hex(8),
                    "type": "income",
                    "amount": float(
                        item.get(
                            "amount",
                            0
                        )
                    ),
                    "category": category,
                    "date": due.isoformat(),
                    "description": name[:200],
                    "created_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "owner": user,
                    "source": "recurring_income",
                    "recurring_id": item.get("id"),
                })

                existing_keys.add(key)

                changed_money = True

            processed_rounds += 1

            # -------------------------
            # ครั้งเดียว
            # -------------------------

            if frequency == "once":

                item["active"] = False
                item["next_date"] = due.isoformat()

                changed_recurring = True

                break

            # -------------------------
            # ทุกเดือน
            # -------------------------

            item["next_date"] = next_month_date(
                int(
                    item.get(
                        "day",
                        due.day
                    )
                ),
                due
            )

            due = valid_date(
                item["next_date"]
            )

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
