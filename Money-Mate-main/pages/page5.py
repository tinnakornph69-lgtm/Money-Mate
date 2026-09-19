"""MoneyMate smart financial insights."""
import json, os, calendar
from flask import session
from collections import defaultdict
from datetime import date
TITLE="Smart Output"
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); FILE=os.path.join(HERE,"money_data.json")

def load():
    if not os.path.exists(FILE): return []
    try:
        with open(FILE,encoding="utf-8") as f: return json.load(f)
    except (OSError,json.JSONDecodeError): return []

def build(query=None):
    items=load(); user=session.get("user"); items=[x for x in items if user and x.get("owner")==user]; today=date.today(); key=today.strftime("%Y-%m"); month=[x for x in items if str(x.get("date",""))[:7]==key]
    inc=sum(float(x.get("amount",0)) for x in month if x.get("type")=="income"); exp=sum(float(x.get("amount",0)) for x in month if x.get("type")=="expense")
    cats={}
    for x in month:
        if x.get("type")=="expense": cats[x.get("category","อื่น ๆ")]=cats.get(x.get("category","อื่น ๆ"),0)+float(x.get("amount",0))
    rate=(inc-exp)/inc if inc else 0; score=round(max(0,min(100,50+rate*50))) if inc else 50
    days=today.day; remaining=max(1,calendar.monthrange(today.year,today.month)[1]-days+1); daily=max(0,(inc-exp)/remaining)
    tips=[]; alerts=[]
    if inc==0: tips.append("เริ่มบันทึกรายรับ เพื่อให้ระบบคำนวณสุขภาพการเงินได้แม่นขึ้น")
    elif exp>inc: alerts.append("รายจ่ายเดือนนี้สูงกว่ารายรับที่บันทึกไว้")
    elif exp>inc*0.8: alerts.append("รายจ่ายใช้สัดส่วนสูงของรายรับ ควรติดตามหมวดที่ใช้มาก")
    else: tips.append("รายรับยังมากกว่ารายจ่าย ลองกันเงินส่วนหนึ่งไว้เป็นเงินออม")
    if cats:
        top=max(cats,key=cats.get); tips.append(f"หมวดที่ใช้มากที่สุดเดือนนี้คือ {top} ({cats[top]:,.2f} บาท)")
    days_in_month=calendar.monthrange(today.year,today.month)[1]
    projected_expense=(exp/today.day)*days_in_month if exp and today.day else exp
    forecast=inc-projected_expense
    historical=defaultdict(list)
    for x in items:
        if x.get("type")=="expense":
            historical[x.get("category","อื่น ๆ")].append(float(x.get("amount",0)))
    for category, current in cats.items():
        history=historical.get(category,[])
        if len(history)>=3:
            avg=sum(history)/len(history)
            if current > avg*1.5:
                alerts.append(f"หมวด {category} สูงกว่าค่าเฉลี่ยที่บันทึกไว้ประมาณ 50% ขึ้นไป")
    return {"income":inc,"expense":exp,"score":score,"daily_limit":daily,"forecast":forecast,"tips":tips,"alerts":alerts,"categories":sorted(cats.items(),key=lambda p:p[1],reverse=True)[:5],"month":key,"projected_expense":projected_expense}
