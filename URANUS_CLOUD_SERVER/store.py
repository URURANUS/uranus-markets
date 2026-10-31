"""
store.py — المستخدمون، قوائم المتابعة، التنبيهات (SQLite عبر sqlite3 القياسي).

ملاحظة معمارية: SQLite كافية حتى آلاف المستخدمين مع WAL mode.
عند الحاجة لما بعدها: نفس الواجهة تُستبدل بـ PostgreSQL دون تغيير main.py.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time
from typing import Any

import jwt  # PyJWT

_DB_PATH = os.path.join(os.path.dirname(__file__), "markets.db")
JWT_SECRET = os.environ.get("MARKETS_JWT_SECRET", "change-me-in-production")
TOKEN_HOURS = 24 * 7


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS watchlist(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, market, symbol)
        );
        CREATE TABLE IF NOT EXISTS alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('above','below')),
            target_price REAL NOT NULL,
            active INTEGER DEFAULT 1,
            triggered_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)


# ─────────────────────────────── كلمات المرور ───────────────────────────────
def _hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000)
    return salt.hex() + "$" + dk.hex()


def _verify_pw(pw: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 120_000)
        return hmac.compare_digest(calc.hex(), dk_hex)
    except Exception:
        return False


# ─────────────────────────────── التوكنات JWT ───────────────────────────────
def make_token(user_id: int, username: str) -> str:
    return jwt.encode({"uid": user_id, "u": username, "exp": int(time.time()) + TOKEN_HOURS * 3600},
                      JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


# ─────────────────────────────── المستخدمون ─────────────────────────────────
def register(username: str, password: str) -> dict[str, Any] | str:
    if len(password) < 6:
        return "كلمة المرور يجب أن تكون 6 أحرف على الأقل"
    if not username or len(username) < 3:
        return "اسم المستخدم قصير جداً"
    with _conn() as c:
        if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return "اسم المستخدم محجوز"
        cur = c.execute("INSERT INTO users(username,pw_hash) VALUES(?,?)",
                        (username, _hash_pw(password)))
        uid = cur.lastrowid
    return {"user_id": uid, "username": username, "token": make_token(uid, username)}


def login(username: str, password: str) -> dict[str, Any] | str:
    with _conn() as c:
        row = c.execute("SELECT id,username,pw_hash FROM users WHERE username=?",
                        (username,)).fetchone()
    if not row or not _verify_pw(password, row["pw_hash"]):
        return "بيانات الدخول غير صحيحة"
    return {"user_id": row["id"], "username": row["username"],
            "token": make_token(row["id"], row["username"])}


# ─────────────────────────────── قائمة المتابعة ─────────────────────────────
def wl_add(uid: int, market: str, symbol: str) -> dict:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO watchlist(user_id,market,symbol) VALUES(?,?,?)",
                  (uid, market.lower(), symbol.upper()))
    return {"detail": f"{symbol.upper()} added."}


def wl_remove(uid: int, item_id: int) -> dict:
    with _conn() as c:
        c.execute("DELETE FROM watchlist WHERE id=? AND user_id=?", (item_id, uid))
    return {"detail": "removed"}


def wl_list(uid: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT id,market,symbol FROM watchlist WHERE user_id=? ORDER BY id",
                         (uid,)).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────── التنبيهات ──────────────────────────────
def alert_add(uid: int, market: str, symbol: str, direction: str,
              target: float) -> dict:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO alerts(user_id,market,symbol,direction,target_price)"
            " VALUES(?,?,?,?,?)", (uid, market.lower(), symbol.upper(), direction, target))
        aid = cur.lastrowid
    return {"detail": f"Alert #{aid} created.", "alert_id": aid}


def alert_remove(uid: int, alert_id: int) -> dict:
    with _conn() as c:
        c.execute("DELETE FROM alerts WHERE id=? AND user_id=?", (alert_id, uid))
    return {"detail": "deleted"}


def alerts_list(uid: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC",
                         (uid,)).fetchall()
    return [dict(r) for r in rows]
