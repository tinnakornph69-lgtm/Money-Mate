"""MoneyMate account center: register/login/admin overview."""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from flask import session

TITLE = "เข้าสู่ระบบ / สมัครสมาชิก"

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_FILE = os.path.join(HERE, "accounts.json")
PRESENCE_FILE = os.path.join(HERE, "presence.json")

ADMIN_USERNAME = "admin"


def _load(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save(path, data):
    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(tmp, path)


def _hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        120000
    ).hex()


def _make_password(password):
    salt = secrets.token_hex(16)

    return (
        _hash(password, salt),
        salt
    )


def _valid_username(username):
    """Validate a user-friendly username.

    Allow Thai/Unicode letters, numbers, spaces, underscore, dot and hyphen.
    This makes normal Thai names usable as account usernames while still
    rejecting punctuation that is unsuitable for an account name.
    """
    username = str(username or "").strip()
    if not 3 <= len(username) <= 30:
        return False
    if username.startswith((".", "-", "_")) or username.endswith((".", "-", "_")):
        return False
    return bool(re.fullmatch(r"[\w .-]+", username, flags=re.UNICODE))


def _touch_presence(query):
    client_id = query.get(
        "client_id",
        ""
    ).strip()

    if not client_id:
        return

    data = _load(
        PRESENCE_FILE,
        {
            "visits": 0,
            "clients": {}
        }
    )

    now = time.time()

    clients = data.setdefault(
        "clients",
        {}
    )

    if client_id not in clients:
        data["visits"] = int(
            data.get("visits", 0)
        ) + 1

    clients[client_id] = {
        "last_seen": now
    }

    for key in list(clients):
        try:
            last_seen = float(
                clients[key].get(
                    "last_seen",
                    0
                )
            )
        except (TypeError, ValueError):
            last_seen = 0

        if now - last_seen > 15:
            del clients[key]

    _save(
        PRESENCE_FILE,
        data
    )


def build(query=None):
    query = query or {}

    if session.get("user"):
        return {"redirect_home": True}

    _touch_presence(query)

    accounts = _load(
        ACCOUNTS_FILE,
        {
            "users": [],
            "admin": {}
        }
    )

    presence = _load(
        PRESENCE_FILE,
        {
            "visits": 0,
            "clients": {}
        }
    )

    current_username = session.get("user")
    profile = None
    if current_username and not session.get("is_admin"):
        for user in accounts.get("users", []):
            if user.get("username", "").lower() == str(current_username).lower():
                profile = {
                    "id": user.get("id", ""),
                    "username": user.get("username", ""),
                    "created_at": user.get("created_at", ""),
                }
                break

    return {
        "users": accounts.get("users", []),
        "visitor_count": int(presence.get("visits", 0)),
        "active_count": len(presence.get("clients", {})),
        "view": query.get("view", "profile") if current_username else "account",
        "profile": profile,
        "client_id": query.get("client_id", ""),
    }


def handle(form):
    action = form.get(
        "action",
        ""
    ).strip()

    username = re.sub(r"\s+", " ", str(form.get(
        "username",
        ""
    )).strip())

    password = form.get(
        "password",
        ""
    )

    # ==========================================
    # REGISTER
    # ==========================================

    if action == "register":

        if not _valid_username(username):
            return (
                "ชื่อผู้ใช้ต้องมี 3–30 ตัวอักษร "
                "และใช้ตัวอักษร/ตัวเลข/_ เท่านั้น"
            )

        if len(password) < 6:
            return (
                "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร"
            )

        accounts = _load(
            ACCOUNTS_FILE,
            {
                "users": [],
                "admin": {}
            }
        )

        users = accounts.setdefault(
            "users",
            []
        )

        if (
            username.lower() == ADMIN_USERNAME
            or any(
                u.get(
                    "username",
                    ""
                ).lower()
                == username.lower()
                for u in users
            )
        ):
            return "ชื่อผู้ใช้นี้ถูกใช้แล้ว"

        password_hash, salt = _make_password(
            password
        )

        users.append(
            {
                "id": secrets.token_hex(8),
                "username": username,
                "password_hash": password_hash,
                "salt": salt,
                "created_at": time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "transactions": []
            }
        )

        _save(
            ACCOUNTS_FILE,
            accounts
        )

        return (
            "สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ"
        )

    # ==========================================
    # LOGOUT
    # ==========================================

    if action == "logout":

        session.clear()

        return "redirect:/"

    # ==========================================
    # LOGIN
    # ==========================================

    if action == "login":

        accounts = _load(
            ACCOUNTS_FILE,
            {
                "users": [],
                "admin": {}
            }
        )

        admin = accounts.get(
            "admin",
            {}
        )

        # --------------------------------------
        # ADMIN LOGIN
        # --------------------------------------

        admin_username = admin.get(
            "username",
            ADMIN_USERNAME
        )

        admin_hash = admin.get(
            "password_hash",
            ""
        )

        admin_salt = admin.get(
            "salt",
            ""
        )

        if (
            username == admin_username
            and admin_hash
            and admin_salt
            and hmac.compare_digest(
                _hash(
                    password,
                    admin_salt
                ),
                admin_hash
            )
        ):

            session.clear()

            session.permanent = True

            session["user"] = admin_username
            session["is_admin"] = True

            # redirect ไปหน้า Admin
            return "redirect:/page10"

        # --------------------------------------
        # NORMAL USER LOGIN
        # --------------------------------------

        for user in accounts.get(
            "users",
            []
        ):

            saved_username = user.get(
                "username",
                ""
            )

            saved_hash = user.get(
                "password_hash",
                ""
            )

            saved_salt = user.get(
                "salt",
                ""
            )

            if (
                saved_username.lower()
                == username.lower()
                and saved_hash
                and saved_salt
                and hmac.compare_digest(
                    _hash(
                        password,
                        saved_salt
                    ),
                    saved_hash
                )
            ):

                session.clear()

                session.permanent = True

                session["user"] = saved_username
                session["is_admin"] = False

                # redirect ไปหน้ารายรับ-รายจ่าย
                return "redirect:/page3"

        return (
            "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
        )

    return "บันทึกเรียบร้อย"