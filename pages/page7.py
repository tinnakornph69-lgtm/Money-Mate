import os
import math
from datetime import date, datetime, timedelta
from flask import has_request_context, session
from persistent_store import read_json, write_json

TITLE = "เงินออมและงบประมาณ"
MAX_AUTO_SAVE_CATCHUP = 366

HERE = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATA_FILE = os.path.join(HERE, "money_data.json")
SAVINGS_FILE = os.path.join(HERE, "savings_data.json")


# =========================================================
# โหลด / บันทึกข้อมูล
# =========================================================

def load_savings():
    data = read_json(SAVINGS_FILE, [])
    return data if isinstance(data, list) else []


def save_savings(data):
    write_json(SAVINGS_FILE, data)


def load_money():
    data = read_json(DATA_FILE, [])
    return data if isinstance(data, list) else []


def save_money(data):
    write_json(DATA_FILE, data)


# =========================================================
# ฟังก์ชันช่วย
# =========================================================

def money(value):
    try:
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        value = float(value)
        return value if math.isfinite(value) else None

    except (ValueError, TypeError):
        return None


def valid_date(value):
    if not value:
        return False

    try:
        date.fromisoformat(str(value))
        return True

    except ValueError:
        return False


def next_day(value):
    current = date.fromisoformat(value)

    return (
        current + timedelta(days=1)
    ).isoformat()


def next_week(value):
    current = date.fromisoformat(value)

    return (
        current + timedelta(days=7)
    ).isoformat()


def next_month(value):
    current = date.fromisoformat(value)

    year = current.year
    month = current.month + 1

    if month > 12:
        year += 1
        month = 1

    days_in_month = [
        31,
        29 if year % 4 == 0 and (
            year % 100 != 0 or
            year % 400 == 0
        ) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31
    ]

    day = min(
        current.day,
        days_in_month[month - 1]
    )

    return date(
        year,
        month,
        day
    ).isoformat()


# =========================================================
# ยอดเงินคงเหลือ
# =========================================================

def get_balance(user):

    if not user:
        return 0

    items = load_money()

    income = 0
    expense = 0

    for item in items:

        if item.get("owner") != user:
            continue

        amount = money(
            item.get("amount")
        )

        if amount is None or amount <= 0:
            continue

        if item.get("type") == "income":
            income += amount

        elif item.get("type") == "expense":
            expense += amount

    return max(0.0, income - expense)


def get_balance_from_items(items, user):
    """คำนวณยอดคงเหลือจากรายการที่อยู่ในหน่วยความจำปัจจุบัน"""
    if not user:
        return 0

    balance = 0

    for item in items:
        if item.get("owner") != user:
            continue

        amount = money(item.get("amount"))
        if amount is None or amount <= 0:
            continue

        if item.get("type") == "income":
            balance += amount
        elif item.get("type") == "expense":
            balance -= amount

    return max(0.0, balance)


# =========================================================
# ดึงเป้าหมายของผู้ใช้
# =========================================================

def get_goals(user):

    if not user:
        return []

    data = load_savings()

    return [
        goal
        for goal in data
        if goal.get("owner") == user
    ]


# =========================================================
# คำนวณแผนออม
# =========================================================

def calculate_plan(
    remaining,
    frequency,
    deadline=None,
    saving_amount=None
):

    remaining = money(remaining) or 0
    saving_amount = money(saving_amount)

    if remaining <= 0:

        return {
            "saving_amount": 0,
            "rounds": 0,
            "days_left": 0
        }

    today = date.today()

    # -----------------------------------------------------
    # มีวันครบกำหนด
    # -----------------------------------------------------

    if deadline and valid_date(deadline):

        deadline_date = date.fromisoformat(
            deadline
        )

        days_left = max(
            0,
            (deadline_date - today).days
        )

        if frequency == "daily":

            rounds = max(
                1,
                days_left + 1
            )

        elif frequency == "weekly":

            rounds = max(
                1,
                (days_left // 7) + 1
            )

        elif frequency == "monthly":

            rounds = 1
            current = today

            while current < deadline_date:

                year = current.year
                month = current.month + 1

                if month > 12:
                    year += 1
                    month = 1

                days_in_month = [
                    31,
                    29 if year % 4 == 0 and (
                        year % 100 != 0 or
                        year % 400 == 0
                    ) else 28,
                    31,
                    30,
                    31,
                    30,
                    31,
                    31,
                    30,
                    31,
                    30,
                    31
                ]

                day = min(
                    current.day,
                    days_in_month[month - 1]
                )

                current = date(
                    year,
                    month,
                    day
                )

                if current <= deadline_date:
                    rounds += 1

        else:
            rounds = 1

        if (
            saving_amount is None
            or saving_amount <= 0
        ):

            if rounds > 0:
                saving_amount = (
                    remaining / rounds
                )
            else:
                saving_amount = remaining

        return {
            "saving_amount": round(
                saving_amount,
                2
            ),
            "rounds": rounds,
            "days_left": days_left
        }

    # -----------------------------------------------------
    # ไม่มี deadline
    # -----------------------------------------------------

    if (
        saving_amount is None
        or saving_amount <= 0
    ):

        return {
            "saving_amount": 0,
            "rounds": 0,
            "days_left": 0
        }

    return {
        "saving_amount": round(
            saving_amount,
            2
        ),
        "rounds": 0,
        "days_left": 0
    }


# =========================================================
# วันที่ออมรอบถัดไป
# =========================================================

def get_next_saving_date(goal):

    today = date.today().isoformat()

    next_date = goal.get(
        "next_saving_date"
    )

    if not next_date:
        return today

    if not valid_date(next_date):
        return today

    return next_date


# =========================================================
# ออมอัตโนมัติ
# =========================================================

def process_auto_saving(user):

    if not user:
        return

    savings = load_savings()
    money_data = load_money()

    today = date.today()

    changed_savings = False
    changed_money = False
    available_balance = get_balance_from_items(
        money_data,
        user
    )

    for goal in savings:

        if goal.get("owner") != user:
            continue

        if not goal.get("auto_save"):
            continue

        target = money(
            goal.get("target")
        ) or 0

        saved = money(
            goal.get("saved")
        ) or 0

        remaining = max(
            0,
            target - saved
        )

        goal["remaining"] = round(
            remaining,
            2
        )

        if remaining <= 0:

            goal["auto_save"] = False
            goal["next_saving_date"] = ""

            changed_savings = True

            continue

        frequency = goal.get(
            "frequency",
            ""
        )

        if frequency not in [
            "daily",
            "weekly",
            "monthly"
        ]:
            goal["auto_save"] = False
            goal["next_saving_date"] = ""
            changed_savings = True
            continue

        saving_amount = money(
            goal.get("saving_amount")
        )

        if (
            saving_amount is None
            or saving_amount <= 0
        ):
            continue

        next_date = get_next_saving_date(
            goal
        )

        if not valid_date(next_date):
            next_date = today.isoformat()

        next_date_obj = date.fromisoformat(
            next_date
        )

        # -------------------------------------------------
        # ประมวลผลทุกงวดที่ถึงกำหนด
        # -------------------------------------------------

        processed_rounds = 0

        while (
            next_date_obj <= today
            and remaining > 0
            and processed_rounds < MAX_AUTO_SAVE_CATCHUP
        ):

            if available_balance <= 0:
                break

            amount = min(
                saving_amount,
                remaining,
                available_balance
            )

            if amount <= 0:
                break

            old_saved = money(
                goal.get("saved")
            ) or 0

            new_saved = old_saved + amount

            goal["saved"] = round(
                new_saved,
                2
            )

            remaining = max(
                0,
                target - new_saved
            )

            goal["remaining"] = round(
                remaining,
                2
            )

            transaction = {
                "id": (
                    f"saving_"
                    f"{goal.get('id', '')}_"
                    f"{datetime.now().timestamp()}"
                ),
                "owner": user,
                "type": "expense",
                "amount": round(
                    amount,
                    2
                ),
                "category": "เงินออม",
                "description": (
                    "ออมอัตโนมัติ: "
                    f"{goal.get('name', 'เป้าหมาย')}"
                ),
                "date": (
                    next_date_obj.isoformat()
                ),
                "created_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "source": "auto_saving",
                "saving_goal_id": str(
                    goal.get("id", "")
                )
            }

            money_data.append(
                transaction
            )

            available_balance = max(
                0,
                available_balance - amount
            )
            processed_rounds += 1

            changed_savings = True
            changed_money = True

            # -------------------------------------------------
            # สำเร็จ
            # -------------------------------------------------

            if remaining <= 0:

                goal["auto_save"] = False
                goal["next_saving_date"] = ""

                break

            # -------------------------------------------------
            # รอบถัดไป
            # -------------------------------------------------

            if frequency == "daily":

                next_date = next_day(
                    next_date_obj.isoformat()
                )

            elif frequency == "weekly":

                next_date = next_week(
                    next_date_obj.isoformat()
                )

            elif frequency == "monthly":

                next_date = next_month(
                    next_date_obj.isoformat()
                )

            next_date_obj = date.fromisoformat(
                next_date
            )

            goal["next_saving_date"] = next_date

    if changed_savings:
        save_savings(savings)

    if changed_money:
        save_money(money_data)


# =========================================================
# สร้างข้อมูลให้ page7.html
# =========================================================

def build(query=None):

    user = session.get("user")

    if not user:

        return {
            "goals": [],
            "balance": 0,
            "total_saved": 0
        }

    process_auto_saving(user)

    goals = get_goals(user)

    total_saved = 0

    for goal in goals:

        target = money(
            goal.get("target")
        ) or 0

        saved = money(
            goal.get("saved")
        ) or 0

        remaining = max(
            0,
            target - saved
        )

        goal["target"] = round(
            target,
            2
        )

        goal["saved"] = round(
            saved,
            2
        )

        goal["remaining"] = round(
            remaining,
            2
        )

        if target > 0:

            progress = (
                saved / target
            ) * 100

            goal["progress"] = round(
                min(100, progress),
                1
            )

        else:

            goal["progress"] = 0

        total_saved += saved

        # -------------------------------------------------
        # คำนวณข้อมูล Auto Save
        # -------------------------------------------------

        if goal.get("auto_save"):

            plan = calculate_plan(
                remaining,
                goal.get(
                    "frequency",
                    ""
                ),
                goal.get(
                    "deadline"
                ),
                goal.get(
                    "saving_amount"
                )
            )

            if plan["saving_amount"] > 0:

                goal["saving_amount"] = (
                    plan["saving_amount"]
                )

            goal["rounds"] = (
                plan["rounds"]
            )

            goal["days_left"] = (
                plan["days_left"]
            )

    return {
        "goals": goals,
        "balance": round(
            get_balance(user),
            2
        ),
        "total_saved": round(
            total_saved,
            2
        )
    }


# =========================================================
# เพิ่มเป้าหมาย
# =========================================================

def add_goal(form, user):

    if not user:
        return "กรุณาเข้าสู่ระบบก่อน"

    name = str(
        form.get("name", "")
    ).strip()

    target_raw = str(
        form.get("target", "")
    ).strip()

    saved_raw = str(
        form.get("saved", "")
    ).strip()

    deadline = str(
        form.get("deadline", "")
    ).strip()

    # -----------------------------------------------------
    # ตรวจชื่อ
    # -----------------------------------------------------

    if not name:
        return "กรุณากรอกชื่อเป้าหมาย"

    # -----------------------------------------------------
    # ตรวจเป้าหมาย
    # -----------------------------------------------------

    if not target_raw:
        return "กรุณากรอกจำนวนเงินเป้าหมาย"

    target = money(target_raw)

    if target is None or target <= 0:
        return "กรุณากรอกจำนวนเงินเป้าหมายให้ถูกต้อง"

    # -----------------------------------------------------
    # เงินที่มีอยู่แล้ว
    # -----------------------------------------------------

    if saved_raw == "":
        saved = 0
    else:
        saved = money(saved_raw)

    if saved is None:
        return "กรุณากรอกเงินที่มีอยู่แล้วให้ถูกต้อง"

    if saved < 0:
        return "เงินที่มีอยู่แล้วไม่สามารถติดลบได้"

    if saved > target:
        return "เงินที่ออมแล้วต้องไม่มากกว่าเป้าหมาย"

    # -----------------------------------------------------
    # Deadline
    # -----------------------------------------------------

    if deadline and not valid_date(deadline):
        return "รูปแบบวันที่ไม่ถูกต้อง"

    if deadline and date.fromisoformat(deadline) < date.today():
        return "วันครบกำหนดต้องเป็นวันนี้หรือวันในอนาคต"

    # -----------------------------------------------------
    # Auto Save
    # -----------------------------------------------------

    auto_save = (
        form.get("auto_save")
        in [
            "1",
            "on",
            "true",
            "yes"
        ]
    )

    frequency = str(
        form.get("frequency", "")
    ).strip()

    saving_amount_raw = str(
        form.get("saving_amount", "")
    ).strip()

    saving_amount = money(
        saving_amount_raw
    )

    remaining = max(
        0,
        target - saved
    )

    if auto_save:

        # ต้องเลือกความถี่
        if frequency not in [
            "daily",
            "weekly",
            "monthly"
        ]:

            return (
                "กรุณาเลือกช่วงเวลาการออม"
            )

        # -------------------------------------------------
        # ไม่กรอกเงินต่อรอบ
        # -------------------------------------------------

        if (
            saving_amount is None
            or saving_amount <= 0
        ):

            # ถ้าไม่มี deadline ด้วย
            # ต้องให้กรอกเงินต่อรอบ
            if not deadline:

                return (
                    "กรุณากรอกจำนวนเงิน"
                    "ที่จะออมต่อรอบ "
                    "หรือกำหนดวันครบกำหนด"
                )

            # มี deadline ให้คำนวณ
            plan = calculate_plan(
                remaining,
                frequency,
                deadline,
                None
            )

            saving_amount = (
                plan["saving_amount"]
            )

            if saving_amount <= 0:

                return (
                    "ไม่สามารถคำนวณ"
                    "จำนวนเงินออมต่อรอบได้"
                )

    else:

        frequency = ""
        saving_amount = 0

    # -----------------------------------------------------
    # โหลดข้อมูลเดิม
    # -----------------------------------------------------

    savings = load_savings()

    # -----------------------------------------------------
    # สร้าง ID
    # -----------------------------------------------------

    goal_id = (
        "goal_"
        f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    )

    # -----------------------------------------------------
    # วันที่เริ่มออม
    # -----------------------------------------------------

    if auto_save:
        next_saving_date = (
            date.today().isoformat()
        )
    else:
        next_saving_date = ""

    # -----------------------------------------------------
    # สร้างเป้าหมาย
    # -----------------------------------------------------

    goal = {
        "id": goal_id,
        "owner": user,
        "name": name,
        "target": round(
            target,
            2
        ),
        "saved": round(
            saved,
            2
        ),
        "remaining": round(
            remaining,
            2
        ),
        "deadline": deadline,
        "auto_save": auto_save,
        "frequency": frequency,
        "saving_amount": round(
            saving_amount or 0,
            2
        ),
        "next_saving_date": (
            next_saving_date
        ),
        "created_at": (
            datetime.now().isoformat()
        )
    }

    # เงินตั้งต้นในเป้าหมายถือเป็นเงินจริงที่กันออกจากยอดใช้ได้
    if saved > get_balance(user) + 1e-9:
        return f"ยอดเงินคงเหลือไม่เพียงพอสำหรับเงินตั้งต้น (คงเหลือ {get_balance(user):,.2f} บาท)"

    savings.append(goal)
    save_savings(savings)

    if saved > 0:
        money_data = load_money()
        money_data.append({
            "id": f"saving_{goal_id}_{datetime.now().timestamp()}",
            "owner": user, "type": "expense", "amount": round(saved, 2),
            "category": "เงินออม", "description": f"เงินตั้งต้นเป้าหมาย: {name}",
            "date": date.today().isoformat(), "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "manual_saving", "saving_goal_id": goal_id,
        })
        save_money(money_data)

    return "เพิ่มเป้าหมายการออมเรียบร้อยแล้ว"


# =========================================================
# แก้เงินออมต่อรอบ
# =========================================================

def update_saving_amount(form, user):

    if not user:
        return "กรุณาเข้าสู่ระบบก่อน"

    goal_id = str(
        form.get("goal_id", "")
    ).strip()

    amount_raw = str(
        form.get("saving_amount", "")
    ).strip()

    requested_frequency = str(
        form.get("frequency", "")
    ).strip()

    # -----------------------------------------------------
    # ตรวจข้อมูล
    # -----------------------------------------------------

    if not goal_id:
        return "ไม่พบเป้าหมาย"

    if not amount_raw:
        return (
            "กรุณากรอกเงินออมต่อรอบ"
        )

    amount = money(amount_raw)

    if amount is None or amount <= 0:
        return (
            "กรุณากรอกเงินออมต่อรอบ"
            "ให้มากกว่า 0"
        )

    savings = load_savings()

    for goal in savings:

        if (
            str(goal.get("id"))
            == goal_id
            and goal.get("owner") == user
        ):

            # ---------------------------------------------
            # ต้องมีความถี่
            # ---------------------------------------------

            frequency = (
                requested_frequency
                or str(goal.get("frequency", "")).strip()
            )

            if frequency not in [
                "daily",
                "weekly",
                "monthly"
            ]:

                return (
                    "กรุณากำหนด"
                    "ช่วงเวลาการออมก่อน"
                )

            goal["frequency"] = frequency

            # ---------------------------------------------
            # เปลี่ยนจำนวนเงิน
            # ---------------------------------------------

            goal["saving_amount"] = round(
                amount,
                2
            )

            # เปิด Auto Save ให้ด้วย
            goal["auto_save"] = True

            # ---------------------------------------------
            # เริ่มนับรอบใหม่จากวันนี้
            # ---------------------------------------------

            goal["next_saving_date"] = (
                date.today().isoformat()
            )

            save_savings(savings)

            return (
                "แก้ไขเงินออมต่อรอบเรียบร้อยแล้ว"
            )

    return "ไม่พบเป้าหมาย"


# =========================================================
# เพิ่มเงินออมด้วยตัวเอง
# =========================================================

def add_saving(form, user):

    if not user:
        return "กรุณาเข้าสู่ระบบก่อน"

    goal_id = str(
        form.get("goal_id", "")
    ).strip()

    amount_raw = str(
        form.get("amount", "")
    ).strip()

    if not goal_id:
        return "ไม่พบเป้าหมาย"

    if not amount_raw:
        return (
            "กรุณากรอกจำนวนเงินที่ต้องการออม"
        )

    amount = money(amount_raw)

    if amount is None or amount <= 0:
        return (
            "กรุณากรอกจำนวนเงิน"
            "ที่ต้องการออมให้ถูกต้อง"
        )

    savings = load_savings()

    found = None

    for goal in savings:

        if (
            str(goal.get("id"))
            == goal_id
            and goal.get("owner") == user
        ):

            found = goal
            break

    if found is None:
        return "ไม่พบเป้าหมายการออม"

    target = money(
        found.get("target")
    ) or 0

    saved = money(
        found.get("saved")
    ) or 0

    remaining = max(
        0,
        target - saved
    )

    if remaining <= 0:
        return (
            "เป้าหมายนี้สำเร็จแล้ว"
        )

    amount = min(amount, remaining)

    available = get_balance(user)
    if amount > available + 1e-9:
        return f"ยอดเงินคงเหลือไม่เพียงพอ (คงเหลือ {available:,.2f} บาท)"

    # -----------------------------------------------------
    # เพิ่มยอดออม
    # -----------------------------------------------------

    found["saved"] = round(
        saved + amount,
        2
    )

    found["remaining"] = round(
        target - found["saved"],
        2
    )

    # -----------------------------------------------------
    # เพิ่มรายการเงินออม
    # -----------------------------------------------------

    money_data = load_money()

    money_data.append({
        "id": (
            f"saving_"
            f"{goal_id}_"
            f"{datetime.now().timestamp()}"
        ),
        "owner": user,
        "type": "expense",
        "amount": round(
            amount,
            2
        ),
        "category": "เงินออม",
        "description": (
            "ออมเงิน: "
            f"{found.get('name', 'เป้าหมาย')}"
        ),
        "date": date.today().isoformat(),
        "source": "manual_saving"
    })

    # -----------------------------------------------------
    # เป้าหมายสำเร็จ
    # -----------------------------------------------------

    if found["remaining"] <= 0:

        found["auto_save"] = False
        found["next_saving_date"] = ""

    save_savings(savings)
    save_money(money_data)

    return (
        "เพิ่มเงินออมเรียบร้อยแล้ว"
    )


# =========================================================
# เปิด / ปิดออมอัตโนมัติ
# =========================================================

def toggle_auto_save(form, user):

    if not user:
        return "กรุณาเข้าสู่ระบบก่อน"

    goal_id = str(
        form.get("goal_id", "")
    ).strip()

    if not goal_id:
        return "ไม่พบเป้าหมาย"

    savings = load_savings()

    for goal in savings:

        if (
            str(goal.get("id"))
            == goal_id
            and goal.get("owner") == user
        ):

            current_status = bool(
                goal.get("auto_save")
            )

            # -------------------------------------------------
            # ถ้ากำลังจะเปิด
            # -------------------------------------------------

            if not current_status:

                frequency = goal.get(
                    "frequency",
                    ""
                )

                if frequency not in [
                    "daily",
                    "weekly",
                    "monthly"
                ]:

                    return (
                        "กรุณากำหนด"
                        "ช่วงเวลาการออมก่อน"
                    )

                remaining = money(
                    goal.get("remaining")
                )

                if remaining is None:

                    target = money(
                        goal.get("target")
                    ) or 0

                    saved = money(
                        goal.get("saved")
                    ) or 0

                    remaining = max(
                        0,
                        target - saved
                    )

                saving_amount = money(
                    goal.get(
                        "saving_amount"
                    )
                )

                if (
                    saving_amount is None
                    or saving_amount <= 0
                ):

                    plan = calculate_plan(
                        remaining,
                        frequency,
                        goal.get(
                            "deadline"
                        ),
                        None
                    )

                    if plan[
                        "saving_amount"
                    ] <= 0:

                        return (
                            "กรุณากำหนด"
                            "จำนวนเงินออม "
                            "หรือวันครบกำหนด"
                        )

                    goal["saving_amount"] = (
                        plan["saving_amount"]
                    )

                goal["auto_save"] = True

                goal["next_saving_date"] = (
                    date.today().isoformat()
                )

            # -------------------------------------------------
            # ถ้ากำลังจะปิด
            # -------------------------------------------------

            else:

                goal["auto_save"] = False

                goal["next_saving_date"] = ""

            save_savings(savings)

            if goal["auto_save"]:

                return (
                    "เปิดการออมอัตโนมัติแล้ว"
                )

            return (
                "ปิดการออมอัตโนมัติแล้ว"
            )

    return "ไม่พบเป้าหมาย"


# =========================================================
# ลบเป้าหมาย
# =========================================================

def delete_goal(form, user):

    if not user:
        return "กรุณาเข้าสู่ระบบก่อน"

    goal_id = str(
        form.get("goal_id", "")
    ).strip()

    if not goal_id:
        return "ไม่พบเป้าหมาย"

    savings = load_savings()

    new_data = []

    found = False

    for goal in savings:

        if (
            str(goal.get("id"))
            == goal_id
            and goal.get("owner") == user
        ):

            found = True
            continue

        new_data.append(goal)

    if not found:
        return "ไม่พบเป้าหมาย"

    save_savings(new_data)

    return (
        "ลบเป้าหมายเรียบร้อยแล้ว"
    )


# =========================================================
# รับคำสั่งจาก app.py
# =========================================================


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

    action = str(
        form.get("action", "")
    ).strip()

    if action == "bulk_delete_goals":
        selected = set(_selected_values(form, "selected_ids"))
        if not selected:
            return "กรุณาเลือกเป้าหมายที่ต้องการลบ"
        items = load_savings()
        kept = [x for x in items if not (x.get("owner") == user and str(x.get("id")) in selected)]
        deleted = len(items) - len(kept)
        if not deleted:
            return "ไม่พบเป้าหมายที่ต้องการลบ"
        save_savings(kept)
        return f"ลบเป้าหมาย {deleted} รายการเรียบร้อยแล้ว"

    if action == "add_goal":

        return add_goal(
            form,
            user
        )

    if action == "update_saving_amount":

        return update_saving_amount(
            form,
            user
        )

    if action == "add_saving":

        return add_saving(
            form,
            user
        )

    if action == "toggle_auto_save":

        return toggle_auto_save(
            form,
            user
        )

    if action == "delete_goal":

        return delete_goal(
            form,
            user
        )

    return "ไม่พบคำสั่งที่ต้องการ"
