"""MoneyMate admin dashboard."""
import json, os, time
from flask import session
TITLE="Admin"
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(name,default):
    path=os.path.join(HERE,name)
    if not os.path.exists(path):return default
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except (OSError,json.JSONDecodeError):return default
def build(query=None):
    if not session.get("is_admin"):
        return {"users": [], "active": 0, "visits": 0, "transactions": 0, "income": 0, "expense": 0, "balance": 0, "admin_username": ""}
    accounts=read("accounts.json",{"users":[],"admin":{}});presence=read("presence.json",{"visits":0,"clients":{}});items=read("money_data.json",[])
    users=accounts.get("users",[]); active=presence.get("clients",{})
    for k in list(active):
        if time.time()-float(active[k].get("last_seen",0))>15:del active[k]
    income=sum(float(x.get("amount",0)) for x in items if x.get("type")=="income");expense=sum(float(x.get("amount",0)) for x in items if x.get("type")=="expense")
    return {"users":users,"active":len(active),"visits":int(presence.get("visits",0)),"transactions":len(items),"income":income,"expense":expense,"balance":income-expense,"admin_username":accounts.get("admin",{}).get("username","admin")}
