"""MoneyMate runtime setup kept outside the course GIVEN files."""

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from flask import abort, redirect, request, session, url_for

from persistent_store import read_json, write_json


HERE = os.path.dirname(os.path.abspath(__file__))


ADMIN_FIXED_SALT = "moneymate-fixed-admin-v1"
ADMIN_FIXED_HASH = "9a9b19b7d4c5a96b36f8d42bbfefec8198427010288d0998909debde6a77f7d7"

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

    if percent >= 81:
        level, level_name, next_percent = 5, "แชมป์", 100
    elif percent >= 51:
        level, level_name, next_percent = 4, "นักสู้", 81
    elif percent >= 31:
        level, level_name, next_percent = 3, "มุ่งมั่น", 51
    elif percent >= 11:
        level, level_name, next_percent = 2, "สดใส", 31
    else:
        level, level_name, next_percent = 1, "เริ่มต้น", 11

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
    actual_balance = max(0.0, income - expense)
    dashboard = {
        "balance": actual_balance,
        "balance_display": "{:,.2f}".format(actual_balance),
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


def _admin_selected(form):
    if hasattr(form, "getlist"):
        return {str(v).strip() for v in form.getlist("selected_users") if str(v).strip()}
    value = form.get("selected_users", [])
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip() for v in value if str(v).strip()}
    value = str(value).strip()
    return {value} if value else set()


def _delete_users_everywhere(usernames):
    """ลบบัญชีและข้อมูลที่มี owner ตรงกับบัญชีที่เลือก."""
    usernames = {str(x).strip() for x in usernames if str(x).strip()}
    if not usernames:
        return 0

    accounts = read_json("accounts.json", {"users": [], "admin": {}})
    if not isinstance(accounts, dict):
        accounts = {"users": [], "admin": {}}
    users = accounts.get("users", [])
    if not isinstance(users, list):
        users = []

    kept_users = [
        item for item in users
        if not (isinstance(item, dict) and str(item.get("username", "")).strip() in usernames)
    ]
    deleted = len(users) - len(kept_users)
    if not deleted:
        return 0
    accounts["users"] = kept_users
    write_json("accounts.json", accounts)

    # User-owned list stores.
    for filename in ("money_data.json", "savings_data.json", "recurring_income.json"):
        data = read_json(filename, [])
        if isinstance(data, list):
            write_json(filename, [
                item for item in data
                if not (isinstance(item, dict) and str(item.get("owner", "")).strip() in usernames)
            ])

    # Budget data can be nested/dict-shaped; recursively remove keys/records owned by deleted users.
    budget = read_json("budget_data.json", {})
    def clean(value):
        if isinstance(value, list):
            return [
                clean(item) for item in value
                if not (isinstance(item, dict) and str(item.get("owner", "")).strip() in usernames)
            ]
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if str(key).strip() in usernames:
                    continue
                if isinstance(item, dict) and str(item.get("owner", "")).strip() in usernames:
                    continue
                result[key] = clean(item)
            return result
        return value
    if isinstance(budget, (dict, list)):
        write_json("budget_data.json", clean(budget))

    presence = read_json("presence.json", {"visits": 0, "clients": {}})
    if isinstance(presence, dict):
        clients = presence.get("clients", {})
        if isinstance(clients, dict):
            presence["clients"] = {
                key: val for key, val in clients.items()
                if not (isinstance(val, dict) and str(val.get("user", "")).strip() in usernames)
            }
            write_json("presence.json", presence)
    return deleted


def _password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 120000
    ).hex()


def _verify_admin_password(password):
    return bool(
        password
        and hmac.compare_digest(
            _password_hash(password, ADMIN_FIXED_SALT),
            ADMIN_FIXED_HASH,
        )
    )


def _reset_user_password(username, new_password):
    accounts = read_json("accounts.json", {"users": [], "admin": {}})
    if not isinstance(accounts, dict):
        return False
    for user in accounts.get("users", []):
        if isinstance(user, dict) and str(user.get("username", "")).lower() == str(username).lower():
            salt = secrets.token_hex(16)
            user["salt"] = salt
            user["password_hash"] = _password_hash(new_password, salt)
            user["must_change_password"] = True
            write_json("accounts.json", accounts)
            return True
    return False


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
        # Admin bulk account deletion. Kept here so course GIVEN files stay unchanged.
        if request.path == "/page10" and request.method == "POST":
            if not session.get("is_admin"):
                abort(403)
            action = request.form.get("action", "").strip()
            if action == "bulk_delete_users":
                supplied = request.form.get("csrf_token", "")
                expected = session.get("csrf_token", "")
                if not supplied or not expected or not hmac.compare_digest(supplied, expected):
                    abort(400, description="คำขอไม่ถูกต้อง กรุณาลองใหม่")
                selected = _admin_selected(request.form)
                # Never delete the currently signed-in administrator.
                selected.discard(str(session.get("user", "")).strip())
                _delete_users_everywhere(selected)
                return redirect(url_for("page", name="page10"))
            if action == "reset_user_password":
                supplied = request.form.get("csrf_token", "")
                expected = session.get("csrf_token", "")
                if not supplied or not expected or not hmac.compare_digest(supplied, expected):
                    abort(400, description="คำขอไม่ถูกต้อง กรุณาลองใหม่")
                admin_password = str(request.form.get("admin_password", ""))
                username = str(request.form.get("username", "")).strip()
                temporary = str(request.form.get("temporary_password", ""))
                if not _verify_admin_password(admin_password):
                    abort(403, description="รหัสผ่านผู้ดูแลไม่ถูกต้อง")
                if len(temporary) < 8:
                    abort(400, description="รหัสผ่านชั่วคราวต้องมีอย่างน้อย 8 ตัวอักษร")
                if not _reset_user_password(username, temporary):
                    abort(404, description="ไม่พบบัญชีผู้ใช้")
                return redirect(url_for("page", name="page10"))

        if session.get("user"):
            session.permanent = True

        if request.path == "/page1" and request.method == "POST":
            if request.form.get("action", "").strip() == "logout":
                session.clear()
                return redirect(url_for("home"))

        # ผู้ใช้ที่ Admin reset รหัสผ่าน ต้องเปลี่ยนรหัสก่อนใช้งานส่วนอื่น
        if (
            session.get("user")
            and not session.get("is_admin")
            and session.get("must_change_password")
            and request.path != "/page1"
        ):
            return redirect(url_for("page", name="page1", view="profile"))

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
            and not session.get("must_change_password")
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
