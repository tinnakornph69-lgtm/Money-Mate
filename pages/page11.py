"""MoneyMate IF Simulator."""
import math
TITLE = "IF Simulator"

def build(query=None):
    q = query or {}
    def num(k, default=0):
        try:
            value = float(q.get(k, default))
            return max(0.0, value) if math.isfinite(value) else float(default)
        except (ValueError, TypeError): return float(default)
    income = num("income")
    expense = num("expense")
    extra = num("extra")
    raw_balance = income - expense
    raw_after = raw_balance - extra
    balance = max(0.0, raw_balance)
    after = max(0.0, raw_after)
    if income <= 0:
        status = "กรอกประมาณการรายรับก่อน เพื่อดูผลจำลอง"
    elif raw_after < 0:
        status = f"เงินไม่เพียงพอ ขาดอีก {abs(raw_after):,.2f} บาท"
    elif after == 0:
        status = "สถานการณ์จำลองนี้ใช้เงินจนหมดพอดี"
    else:
        status = "สถานการณ์จำลองนี้ยังมีเงินเหลือ"
    return {
        "income": income, "expense": expense, "extra": extra,
        "balance": balance, "after": after, "status": status
    }

def handle(form):
    return ""
