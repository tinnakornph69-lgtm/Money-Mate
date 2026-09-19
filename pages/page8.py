"""MoneyMate Smart Input — natural-language transaction entry."""
import os, re, secrets
from datetime import datetime
from flask import session
from persistent_store import read_json, write_json

TITLE = "Smart Input"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONEY_FILE = os.path.join(HERE, "money_data.json")
CATEGORIES = ["อาหาร","เดินทาง","ช้อปปิ้ง","บิล/ค่าใช้จ่าย","การศึกษา","สุขภาพ","ความบันเทิง","เงินเดือน","งานเสริม","อื่น ๆ"]

def resolve_category(form):
    selected = str(form.get("category", "อื่น ๆ")).strip()
    custom = str(form.get("custom_category", "")).strip()
    if selected == "อื่น ๆ" and custom:
        return custom[:60]
    return selected

def load():
    data = read_json(MONEY_FILE, [])
    return data if isinstance(data, list) else []

def save(items):
    write_json(MONEY_FILE, items)

def parse_text(text):
    text = str(text or "").strip()
    if not text:
        return {"name": "", "amount": 0, "raw": ""}

    # ปรับ Pattern ให้รองรับตัวเลขกี่หลักก็ได้ ทั้งแบบคั่นคอมมา (1,250,000) และไม่คั่น (1250000)
    pattern = r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    nums = re.findall(pattern, text)

    amount = 0.0
    if nums:
        try:
            amount = float(nums[-1].replace(",", ""))
        except ValueError:
            amount = 0.0

    name = text
    if nums:
        # ตัดส่วนตัวเลขออกจากข้อความ
        pos = name.rfind(nums[-1])
        if pos >= 0:
            name = name[:pos] + name[pos + len(nums[-1]):]

    name = re.sub(r"(ราคา|จำนวนเงิน|บาท|฿|เงิน)\s*$", "", name, flags=re.I).strip(" -:：")
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = "รายการใหม่"

    return {"name": name, "amount": round(amount, 2), "raw": text}

def build(query=None):
    preview = session.get("smart_input_preview", {})
    if not isinstance(preview, dict):
        preview = {}
    return {"preview": preview, "categories": CATEGORIES}

def handle(form):
    action = form.get("action", "").strip()

    if action == "parse":
        raw = form.get("raw", "").strip()
        parsed = parse_text(raw)
        parsed["type"] = form.get("type", "expense")
        parsed["category"] = form.get("category", "อื่น ๆ")
        parsed["custom_category"] = str(form.get("custom_category", "")).strip()[:60]
        session["smart_input_preview"] = parsed
        return "แยกชื่อและราคาให้แล้ว ตรวจสอบก่อนบันทึก"

    if action == "save":
        if not session.get("user"):
            return "กรุณาเข้าสู่ระบบก่อนบันทึกรายการ"
        name = form.get("name", "").strip() or "รายการใหม่"
        category = resolve_category(form)
        tx_type = form.get("type", "expense").strip()
        try:
            amount = float(form.get("amount", "0"))
        except (ValueError, TypeError):
            return "จำนวนเงินไม่ถูกต้อง"
        if amount <= 0:
            return "จำนวนเงินต้องมากกว่า 0"
        if not category:
            category = "อื่น ๆ"
        if tx_type not in ("income", "expense"):
            tx_type = "expense"

        items = load()
        items.append({
            "id": secrets.token_hex(8),
            "type": tx_type,
            "amount": round(amount, 2),
            "category": category,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "owner": session.get("user")
        })
        save(items)
        session.pop("smart_input_preview", None)
        return "บันทึกรายการจาก Smart Input แล้ว"

    if action == "clear":
        session.pop("smart_input_preview", None)
        return "ล้างข้อมูลแล้ว"

    return ""
