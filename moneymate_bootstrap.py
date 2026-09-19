"""MoneyMate runtime setup kept outside the course GIVEN files."""

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from flask import abort, redirect, request, session, url_for

from persistent_store import read_json


HERE = os.path.dirname(os.path.abspath(__file__))


def _money(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _secret_key():
    configured = (
        os.environ.get("SECRET_KEY", "").strip()
        or os.environ.get("MONEYMATE_SECRET_KEY", "").strip()
    )
    if configured:
        return configured

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        return hashlib.sha256(
            ("MoneyMate-session:" + database_url).encode("utf-8")
        ).hexdigest()

    secret_file = os.path.join(HERE, ".moneymate_secret")
    if os.path.exists(secret_file):
        with open(secret_file, encoding="utf-8") as handle:
            saved = handle.read().strip()
            if saved:
                return saved

    generated = secrets.token_hex(32)
    with open(secret_file, "w", encoding="utf-8") as handle:
        handle.write(generated)
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return generated


def _summaries(user):
    transactions = read_json("money_data.json", [])
    goals = read_json("savings_data.json", [])
    if not isinstance(transactions, list):
        transactions = []
    if not isinstance(goals, list):
        goals = []

    user_transactions = [
        item for item in transactions
        if isinstance(item, dict) and user and item.get("owner") == user
    ]
    user_goals = [
        goal for goal in goals
        if isinstance(goal, dict) and user and goal.get("owner") == user
    ]

    income = sum(
        _money(item.get("amount"))
        for item in user_transactions
        if item.get("type") == "income"
    )
    expense = sum(
        _money(item.get("amount"))
        for item in user_transactions
        if item.get("type") == "expense"
    )
    recent = sorted(
        user_transactions,
        key=lambda item: (str(item.get("date", "")), str(item.get("created_at", ""))),
        reverse=True,
    )[:5]
    for item in recent:
        item["amount_display"] = "{:,.2f}".format(_money(item.get("amount")))
        item["is_income"] = item.get("type") == "income"

    total_saved = sum(_money(goal.get("saved")) for goal in user_goals)
    total_target = sum(_money(goal.get("target")) for goal in user_goals)
    percent = int(min(100, total_saved * 100 / total_target)) if total_target else 0

    if percent >= 80:
        level, level_name, next_percent = 5, "แชมป์", 100
    elif percent >= 60:
        level, level_name, next_percent = 4, "นักสู้", 80
    elif percent >= 40:
        level, level_name, next_percent = 3, "มุ่งมั่น", 60
    elif percent >= 20:
        level, level_name, next_percent = 2, "สดใส", 40
    else:
        level, level_name, next_percent = 1, "เริ่มต้น", 20

    completed = bool(total_target and total_saved >= total_target)
    if completed:
        percent, level, level_name, next_percent = 100, 5, "แชมป์", 100
    next_amount = total_target * next_percent / 100 if total_target else 0.0
    amount_to_next = max(0.0, next_amount - total_saved)

    savings = {
        "count": len(user_goals),
        "total": total_saved,
        "total_display": "{:,.2f}".format(total_saved),
        "target": total_target,
        "target_display": "{:,.2f}".format(total_target),
        "percent": percent,
        "level": level,
        "level_name": level_name,
        "mate_image": "mate-level-{}.svg".format(level),
        "next_percent": next_percent,
        "next_level_amount": next_amount,
        "next_level_display": "{:,.2f}".format(next_amount),
        "amount_to_next": amount_to_next,
        "amount_to_next_display": "{:,.2f}".format(amount_to_next),
        "completed": completed,
        "lit": total_saved > 0,
    }
    dashboard = {
        "balance": income - expense,
        "balance_display": "{:,.2f}".format(income - expense),
        "month_income": income,
        "month_income_display": "{:,.2f}".format(income),
        "month_expense": expense,
        "month_expense_display": "{:,.2f}".format(expense),
        "recent": recent,
    }
    sidebar = dict(savings)
    sidebar["saved_display"] = savings["total_display"]
    sidebar["next_level"] = min(5, level + 1)
    return savings, dashboard, sidebar


def configure(app):
    """Attach account/session/security features without editing app.py."""
    if app.extensions.get("moneymate_configured"):
        return app
    app.extensions["moneymate_configured"] = True

    app.secret_key = _secret_key()
    app.config.update(
        SESSION_COOKIE_NAME="moneymate_session_v3",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("MONEYMATE_SECURE_COOKIE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    @app.before_request
    def money_before_request():
        if session.get("user"):
            session.permanent = True

        if request.path == "/page1" and request.method == "POST":
            if request.form.get("action", "").strip() == "logout":
                session.clear()
                return redirect(url_for("home"))

        # กัน query เดิมของหน้าบัญชีพาผู้ใช้กลับไปหน้าเปลี่ยนรหัสผ่าน
        # หลังเพิ่งล็อกอินสำเร็จ ให้ไปหน้าแรกเสมอ
        if (
            request.path == "/page1"
            and request.method == "GET"
            and session.get("user")
            and session.pop("just_logged_in", False)
        ):
            return redirect(url_for("home"))

        if (
            request.path == "/page1"
            and request.method == "GET"
            and session.get("user")
            and request.args.get("view") != "profile"
            and not (
                request.args.get("msg")
                and not request.args.get("msg", "").startswith("redirect:")
            )
        ):
            return redirect(url_for("page", name="page10") if session.get("is_admin") else url_for("home"))

        if request.path == "/page10" and not session.get("is_admin"):
            return redirect(url_for("home"))

        if request.method == "POST":
            supplied = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not supplied or not expected or not hmac.compare_digest(supplied, expected):
                abort(400, description="คำขอไม่ถูกต้อง กรุณาลองใหม่")

    @app.context_processor
    def money_globals():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        user = session.get("user")
        savings, dashboard, sidebar = _summaries(user)
        return {
            "csrf_token": token,
            "current_user": user,
            "is_admin": bool(session.get("is_admin")),
            "savings_summary": savings,
            "dashboard_summary": dashboard,
            "sidebar_savings": sidebar,
        }

    @app.after_request
    def money_after_request(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        if response.mimetype == "text/html" and response.status_code == 200 and response.data:
            body = response.get_data(as_text=True)
            if "<form" in body and 'name="csrf_token"' not in body:
                hidden = (
                    '<input type="hidden" name="csrf_token" value="'
                    + session.get("csrf_token", "")
                    + '">'
                )
                body = body.replace("</form>", hidden + "</form>")
                response.set_data(body)
        return response

    return app
