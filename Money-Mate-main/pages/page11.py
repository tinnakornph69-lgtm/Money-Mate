"""MoneyMate IF Simulator."""
from datetime import date
TITLE = "IF Simulator"

def build(query=None):
    q = query or {}
    def num(k, default=0):
        try: return max(0.0, float(q.get(k, default)))
        except (ValueError, TypeError): return float(default)
    income = num("income")
    expense = num("expense")
    extra = num("extra")
    balance = income - expense
    after = balance - extra
    if income <= 0:
        status = "กรอกประมาณการรายรับก่อน เพื่อดูผลจำลอง"
    elif after < 0:
        status = "สถานการณ์จำลองนี้ทำให้เงินติดลบ"
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
