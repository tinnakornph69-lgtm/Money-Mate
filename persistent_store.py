"""Persistent JSON-compatible storage for MoneyMate.

Local development keeps using the project's JSON files. On Render (or any
host with ``DATABASE_URL``) the same data is stored in PostgreSQL, so accounts
and financial records survive restarts and new deployments.
"""
import copy
import json
import os
import shutil
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
SAMPLE_FILE = os.path.join(HERE, "data.sample.json")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
_LOCK = threading.RLock()
_DB_READY = False


def _name(path_or_name):
    return os.path.basename(str(path_or_name))


def _path(path_or_name):
    value = str(path_or_name)
    return value if os.path.isabs(value) else os.path.join(HERE, value)


def _connect():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "ตั้งค่า DATABASE_URL แล้ว แต่ยังไม่ได้ติดตั้ง psycopg; "
            "ให้รัน pip install -r requirements.txt"
        ) from exc

    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return psycopg.connect(url, connect_timeout=10)


def _ensure_table(connection):
    global _DB_READY
    if _DB_READY:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS moneymate_storage (
                storage_key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    connection.commit()
    _DB_READY = True


def _read_local(path_or_name, default):
    path = _path(path_or_name)
    if not os.path.exists(path):
        return copy.deepcopy(default)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)


def _write_local(path_or_name, value):
    path = _path(path_or_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path_or_name, default):
    """Read a JSON value from PostgreSQL or the local JSON file."""
    if not DATABASE_URL:
        with _LOCK:
            return _read_local(path_or_name, default)

    key = _name(path_or_name)
    with _LOCK, _connect() as connection:
        _ensure_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT value FROM moneymate_storage WHERE storage_key = %s",
                (key,),
            )
            row = cursor.fetchone()
            if row is not None:
                value = row[0]
                return json.loads(value) if isinstance(value, str) else value

            seed = _read_local(path_or_name, default)
            cursor.execute(
                """
                INSERT INTO moneymate_storage (storage_key, value)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (storage_key) DO NOTHING
                """,
                (key, json.dumps(seed, ensure_ascii=False)),
            )
        connection.commit()
        return seed


def write_json(path_or_name, value):
    """Atomically write a JSON-compatible value."""
    if not DATABASE_URL:
        with _LOCK:
            _write_local(path_or_name, value)
        return

    key = _name(path_or_name)
    payload = json.dumps(value, ensure_ascii=False)
    with _LOCK, _connect() as connection:
        _ensure_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO moneymate_storage (storage_key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (storage_key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, payload),
            )
        connection.commit()


def load():
    return read_json(DATA_FILE, [])


def save(items):
    write_json(DATA_FILE, items)


def reset():
    """Put data.json back to data.sample.json for the course checker."""
    if os.path.exists(SAMPLE_FILE):
        if DATABASE_URL:
            write_json(DATA_FILE, _read_local(SAMPLE_FILE, []))
        else:
            shutil.copyfile(SAMPLE_FILE, DATA_FILE)
        return True
    return False
