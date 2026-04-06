"""
client.py — TCP socket client that connects to the chat server.
"""

import json
import socket
import threading
from typing import Callable

from ..core.config import Config
from .protocol     import MF


class Client:
    """
    Manages a single TCP connection to the Server.

    Callbacks
    ---------
    on_msg(dict)  – called on the receive thread for every incoming message.
    on_err(str)   – called when the connection drops or an error occurs.
    """

    def __init__(
        self,
        username: str,
        on_msg:   Callable[[dict], None],
        on_err:   Callable[[str],  None],
    ):
        self.username  = username
        self._on_msg   = on_msg
        self._on_err   = on_err
        self._sock     = None
        self.connected = False

    # ── Connection ───────────────────────────────────────────────────────────

    def connect(self, mode: str, password: str) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((Config.HOST, Config.PORT))
            self._sock.sendall(
                json.dumps(
                    {"mode": mode, "username": self.username, "password": password}
                ).encode()
            )
            self.connected = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except Exception as e:
            self._on_err(str(e))
            return False

    def disconnect(self):
        self.connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ── Sending ──────────────────────────────────────────────────────────────

    def send(self, text: str, channel: str):
        if not self.connected:
            return
        try:
            self._sock.sendall(MF.pack(MF.chat(self.username, text, channel)))
        except Exception:
            pass

    def send_dm(self, text: str, recipient: str):
        if not self.connected:
            return
        try:
            self._sock.sendall(MF.pack(MF.dm(self.username, recipient, text)))
        except Exception:
            pass

    def send_dm_delete(self, msg_id: int, peer: str):
        self._ctrl({"type": "dm_delete", "id": msg_id, "peer": peer})

    def send_dm_thread_delete(self, peer: str):
        self._ctrl({"type": "dm_thread_delete", "peer": peer})

    def send_ch_add(self, name: str):
        self._ctrl({"type": "ch_add", "name": name})

    def send_ch_rename(self, old: str, new: str):
        self._ctrl({"type": "ch_rename", "old": old, "new": new})

    def send_ch_remove(self, name: str):
        self._ctrl({"type": "ch_remove", "name": name})

    def _ctrl(self, data: dict):
        if not self.connected:
            return
        try:
            self._sock.sendall(MF.pack(data))
        except Exception:
            pass

    # ── Receive loop ─────────────────────────────────────────────────────────

    def _recv_loop(self):
        buf = ""
        while self.connected:
            try:
                chunk = self._sock.recv(Config.BUFFER).decode()
                if not chunk:
                    break
                buf += chunk
                msgs, buf = MF.unpack(buf)
                for m in msgs:
                    self._on_msg(m)
            except Exception:
                break
        self.connected = False
        self._on_err("Disconnected.")
