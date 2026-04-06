"""
database.py — Thread-safe SQLite wrapper.
One connection per thread via threading.local.
"""

import re
import sqlite3
import secrets
import hashlib
import threading

from .config import Config

class DB:
    _local = threading.local()

    # ── Internal helpers ─────────────────────────────────────────────────────

    @classmethod
    def _conn(cls):
        if not getattr(cls._local, "conn", None):
            cls._local.conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
            cls._local.conn.row_factory = sqlite3.Row
            cls._local.conn.execute("PRAGMA journal_mode=WAL")
            cls._local.conn.execute("PRAGMA foreign_keys=ON")
        return cls._local.conn

    @classmethod
    def _ex(cls, sql, params=()):
        c   = cls._conn()
        cur = c.execute(sql, params)
        c.commit()
        return cur

    # ── Init ─────────────────────────────────────────────────────────────────

    @classmethod
    def init(cls):
        cls._ex("""CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            pw_hash  TEXT NOT NULL,
            salt     TEXT NOT NULL,
            created  TEXT DEFAULT (datetime('now'))
        )""")
        cls._ex("""CREATE TABLE IF NOT EXISTS channels (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE NOT NULL COLLATE NOCASE,
            created TEXT DEFAULT (datetime('now'))
        )""")
        cls._ex("""CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            channel   TEXT NOT NULL,
            username  TEXT NOT NULL,
            body      TEXT NOT NULL,
            ts        TEXT NOT NULL,
            created   TEXT DEFAULT (datetime('now'))
        )""")
        cls._ex("""CREATE TABLE IF NOT EXISTS dms (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sender    TEXT NOT NULL,
            recipient TEXT NOT NULL,
            body      TEXT NOT NULL,
            ts        TEXT NOT NULL,
            created   TEXT DEFAULT (datetime('now'))
        )""")
        for ch in Config.DEFAULT_CHANNELS:
            cls._ex("INSERT OR IGNORE INTO channels(name) VALUES(?)", (ch,))

    # ── Users ────────────────────────────────────────────────────────────────

    @classmethod
    def _hash(cls, password, salt):
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 200_000
        ).hex()

    @classmethod
    def register(cls, username, password):
        if not username or not password:
            return False, "Username and password are required."
        if len(username) > 32 or not re.match(r"^\w[\w .'-]{0,31}$", username):
            return False, "Username: 1-32 chars, letters/numbers/spaces only."
        if len(password) < 4:
            return False, "Password must be at least 4 characters."
        try:
            salt = secrets.token_hex(16)
            cls._ex(
                "INSERT INTO users(username,pw_hash,salt) VALUES(?,?,?)",
                (username.strip(), cls._hash(password, salt), salt),
            )
            return True, ""
        except sqlite3.IntegrityError:
            return False, f"Username '{username}' is already taken."

    @classmethod
    def login(cls, username, password):
        row = cls._conn().execute(
            "SELECT username,pw_hash,salt FROM users WHERE username=? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
        if not row:
            return False, "No account found with that username."
        if cls._hash(password, row["salt"]) != row["pw_hash"]:
            return False, "Incorrect password."
        return True, row["username"]

    # ── Channels ─────────────────────────────────────────────────────────────

    @classmethod
    def get_channels(cls):
        return [
            r["name"]
            for r in cls._conn()
            .execute("SELECT name FROM channels ORDER BY id")
            .fetchall()
        ]

    @classmethod
    def add_channel(cls, name):
        try:
            cls._ex("INSERT INTO channels(name) VALUES(?)", (name,))
            return True
        except sqlite3.IntegrityError:
            return False

    @classmethod
    def rename_channel(cls, old, new):
        cls._ex("UPDATE channels SET name=? WHERE name=?", (new, old))
        cls._ex("UPDATE messages SET channel=? WHERE channel=?", (new, old))

    @classmethod
    def remove_channel(cls, name):
        cls._ex("DELETE FROM channels WHERE name=?", (name,))
        cls._ex("DELETE FROM messages WHERE channel=?", (name,))

    # ── Messages ─────────────────────────────────────────────────────────────

    @classmethod
    def save_msg(cls, channel, username, body, ts):
        cls._ex(
            "INSERT INTO messages(channel,username,body,ts) VALUES(?,?,?,?)",
            (channel, username, body, ts),
        )

    @classmethod
    def get_history(cls, channel, limit=Config.HISTORY_LOAD):
        rows = cls._conn().execute(
            "SELECT username,body,ts FROM messages WHERE channel=? "
            "ORDER BY id DESC LIMIT ?",
            (channel, limit),
        ).fetchall()
        return list(reversed(rows))

    # ── DMs ──────────────────────────────────────────────────────────────────

    @classmethod
    def save_dm(cls, sender, recipient, body, ts):
        cur = cls._ex(
            "INSERT INTO dms(sender,recipient,body,ts) VALUES(?,?,?,?)",
            (sender, recipient, body, ts),
        )
        return cur.lastrowid

    @classmethod
    def delete_dm(cls, msg_id, requester):
        row = cls._conn().execute(
            "SELECT id,sender,recipient FROM dms WHERE id=?",
            (msg_id,),
        ).fetchone()
        if not row or row["sender"] != requester:
            return None
        cls._ex("DELETE FROM dms WHERE id=?", (msg_id,))
        return row

    @classmethod
    def delete_dm_thread(cls, requester, peer):
        row = cls._conn().execute(
            "SELECT 1 FROM dms WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) LIMIT 1",
            (requester, peer, peer, requester),
        ).fetchone()
        if not row:
            return None
        cls._ex(
            "DELETE FROM dms WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)",
            (requester, peer, peer, requester),
        )
        return requester, peer

    @classmethod
    def get_dm_history(cls, user_a, user_b, limit=Config.HISTORY_LOAD):
        rows = cls._conn().execute(
            "SELECT id,sender,recipient,body,ts FROM dms "
            "WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) "
            "ORDER BY id DESC LIMIT ?",
            (user_a, user_b, user_b, user_a, limit),
        ).fetchall()
        return list(reversed(rows))

    @classmethod
    def get_dm_peers(cls, username):
        rows = cls._conn().execute(
            "SELECT DISTINCT CASE WHEN sender=? THEN recipient ELSE sender END AS peer "
            "FROM dms WHERE sender=? OR recipient=?",
            (username, username, username),
        ).fetchall()
        return [r["peer"] for r in rows]
