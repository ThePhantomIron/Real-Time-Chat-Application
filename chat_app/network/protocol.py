"""
protocol.py — Wire-format helpers (MF = Message Factory).

All messages are newline-delimited JSON.
"""

import json
import datetime


class MF:
    """Namespace of static factory methods for every message type."""

    # ── Outbound constructors ────────────────────────────────────────────────

    @staticmethod
    def chat(u: str, text: str, ch: str = "general") -> dict:
        return {"type": "msg", "username": u, "text": text,
                "channel": ch, "time": MF._t()}

    @staticmethod
    def dm(sender: str, recipient: str, text: str, msg_id: int | None = None) -> dict:
        data = {
            "type": "dm",
            "username": sender,
            "to": recipient,
            "text": text,
            "time": MF._t(),
        }
        if msg_id is not None:
            data["id"] = msg_id
        return data

    @staticmethod
    def dm_deleted(msg_id: int, peer_a: str, peer_b: str) -> dict:
        return {"type": "dm_deleted", "id": msg_id, "peer_a": peer_a, "peer_b": peer_b}

    @staticmethod
    def dm_thread_deleted(peer_a: str, peer_b: str) -> dict:
        return {"type": "dm_thread_deleted", "peer_a": peer_a, "peer_b": peer_b}

    @staticmethod
    def system(text: str) -> dict:
        return {"type": "sys", "text": text}

    @staticmethod
    def users(lst: list) -> dict:
        return {"type": "users", "users": lst}

    @staticmethod
    def channels(lst: list) -> dict:
        return {"type": "channels", "channels": lst}

    @staticmethod
    def auth_ok(canonical: str) -> dict:
        return {"type": "auth_ok", "username": canonical}

    @staticmethod
    def auth_fail(reason: str) -> dict:
        return {"type": "auth_fail", "reason": reason}

    @staticmethod
    def history(channel: str, rows) -> dict:
        return {
            "type": "history",
            "channel": channel,
            "messages": [
                {"username": r["username"], "text": r["body"], "time": r["ts"]}
                for r in rows
            ],
        }

    @staticmethod
    def dm_history(peer_a: str, peer_b: str, rows) -> dict:
        return {
            "type": "dm_history",
            "peer_a": peer_a,
            "peer_b": peer_b,
            "messages": [
                {"username": r["sender"], "to": r["recipient"],
                 "text": r["body"], "time": r["ts"], "id": r["id"]}
                for r in rows
            ],
        }

    # ── Serialisation ────────────────────────────────────────────────────────

    @staticmethod
    def _t() -> str:
        return datetime.datetime.now().strftime("%H:%M")

    @staticmethod
    def pack(d: dict) -> bytes:
        return (json.dumps(d) + "\n").encode()

    @staticmethod
    def unpack(buf: str) -> tuple[list[dict], str]:
        msgs, rest = [], buf
        while "\n" in rest:
            line, rest = rest.split("\n", 1)
            if line.strip():
                try:
                    msgs.append(json.loads(line))
                except Exception:
                    pass
        return msgs, rest
