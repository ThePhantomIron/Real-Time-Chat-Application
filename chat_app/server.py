"""
server.py — Multi-threaded TCP chat server.
"""

import json
import socket
import threading

from .core.config import Config
from .core.database import DB
from .network.protocol import MF


class Server:
    """
    Listens on Config.HOST:PORT, authenticates clients, and relays messages.
    Each connected client runs in its own daemon thread.
    """

    def __init__(
        self,
        host: str = Config.SERVER_BIND_HOST,
        port: int = Config.PORT,
        server_name: str = "Local Chat",
        server_password: str = "",
    ):
        self.host = host
        self.port = port
        self.server_name = server_name.strip() or "Local Chat"
        self.server_password = server_password
        self.last_error = ""
        self._clients: dict[socket.socket, str] = {}
        self._lock = threading.Lock()
        self._sock = None
        self._up = False

    @property
    def is_running(self) -> bool:
        return self._up

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> bool:
        DB.init()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.listen(20)
            self._up = True
            self.last_error = ""
            threading.Thread(target=self._accept_loop, daemon=True).start()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def stop(self):
        self._up = False
        with self._lock:
            for s in list(self._clients):
                try:
                    s.close()
                except Exception:
                    pass
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ── Accept loop ──────────────────────────────────────────────────────────

    def _accept_loop(self):
        while self._up:
            try:
                conn, _ = self._sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True,
                ).start()
            except Exception:
                break

    # ── Per-client handler ───────────────────────────────────────────────────

    def _handle_client(self, conn: socket.socket):
        name = "?"
        try:
            # ── Auth handshake ──────────────────────────────────────────────
            raw = conn.recv(Config.BUFFER).decode()
            data = json.loads(raw.strip())
            mode = data.get("mode", "login")
            user = data.get("username", "").strip()
            pw = data.get("password", "")
            supplied_server_password = data.get("server_password", "")

            if supplied_server_password != self.server_password:
                conn.sendall(MF.pack(MF.auth_fail("Incorrect server password.")))
                conn.close()
                return

            if mode == "register":
                ok, msg = DB.register(user, pw)
                if not ok:
                    conn.sendall(MF.pack(MF.auth_fail(msg)))
                    conn.close()
                    return
                canonical = user.strip()
            else:
                ok, result = DB.login(user, pw)
                if not ok:
                    conn.sendall(MF.pack(MF.auth_fail(result)))
                    conn.close()
                    return
                canonical = result

            name = canonical
            conn.sendall(MF.pack(MF.auth_ok(canonical)))

            # ── Send initial state ──────────────────────────────────────────
            ch_list = DB.get_channels()
            conn.sendall(MF.pack(MF.channels(ch_list)))

            for ch in ch_list:
                rows = DB.get_history(ch)
                if rows:
                    conn.sendall(MF.pack(MF.history(ch, rows)))

            for peer in DB.get_dm_peers(canonical):
                rows = DB.get_dm_history(canonical, peer)
                if rows:
                    conn.sendall(MF.pack(MF.dm_history(canonical, peer, rows)))

            # ── Register and announce ───────────────────────────────────────
            with self._lock:
                self._clients[conn] = name
            self._broadcast(MF.system(f"🟢 {name} joined"))
            self._push_users()

            # ── Message loop ────────────────────────────────────────────────
            buf = ""
            while self._up:
                chunk = conn.recv(Config.BUFFER).decode()
                if not chunk:
                    break
                buf += chunk
                msgs, buf = MF.unpack(buf)
                for m in msgs:
                    self._dispatch(m, name)

        except Exception:
            pass
        finally:
            with self._lock:
                self._clients.pop(conn, None)
            try:
                conn.close()
            except Exception:
                pass
            if name != "?":
                self._broadcast(MF.system(f"🔴 {name} left"))
                self._push_users()

    def _dispatch(self, m: dict, sender_name: str):
        t = m.get("type")
        if t == "msg":
            DB.save_msg(
                m.get("channel", "general"),
                m.get("username", ""),
                m.get("text", ""),
                m.get("time", ""),
            )
            self._broadcast(m)

        elif t == "dm":
            msg_id = DB.save_dm(m["username"], m["to"], m["text"], m["time"])
            dm_msg = dict(m)
            dm_msg["id"] = msg_id
            self._send_to(m["username"], dm_msg)
            if m["to"] != m["username"]:
                self._send_to(m["to"], dm_msg)

        elif t == "dm_delete":
            deleted = DB.delete_dm(m.get("id"), sender_name)
            if deleted:
                payload = MF.dm_deleted(
                    deleted["id"], deleted["sender"], deleted["recipient"]
                )
                self._send_to(deleted["sender"], payload)
                if deleted["recipient"] != deleted["sender"]:
                    self._send_to(deleted["recipient"], payload)

        elif t == "dm_thread_delete":
            deleted = DB.delete_dm_thread(sender_name, m.get("peer", ""))
            if deleted:
                payload = MF.dm_thread_deleted(deleted[0], deleted[1])
                self._send_to(deleted[0], payload)
                if deleted[1] != deleted[0]:
                    self._send_to(deleted[1], payload)

        elif t == "ch_add":
            ch_name = m.get("name", "").strip().lower().replace(" ", "-")
            if ch_name and DB.add_channel(ch_name):
                self._broadcast(MF.channels(DB.get_channels()))
                self._broadcast(MF.system(f"📢 #{ch_name} created by {sender_name}"))

        elif t == "ch_rename":
            old, new = m.get("old", ""), m.get("new", "")
            if old and new:
                DB.rename_channel(old, new)
                self._broadcast(MF.channels(DB.get_channels()))
                self._broadcast(MF.system(f"✏️  #{old} renamed to #{new}"))

        elif t == "ch_remove":
            ch_name = m.get("name", "")
            if ch_name:
                DB.remove_channel(ch_name)
                self._broadcast(MF.channels(DB.get_channels()))
                self._broadcast(MF.system(f"🗑  #{ch_name} removed by {sender_name}"))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _send_to(self, username: str, data: dict):
        payload = MF.pack(data)
        with self._lock:
            targets = [s for s, n in self._clients.items() if n == username]
        for s in targets:
            try:
                s.sendall(payload)
            except Exception:
                pass

    def _broadcast(self, data: dict):
        payload = MF.pack(data)
        dead = []
        with self._lock:
            targets = list(self._clients)
        for s in targets:
            try:
                s.sendall(payload)
            except Exception:
                dead.append(s)
        if dead:
            with self._lock:
                for s in dead:
                    self._clients.pop(s, None)

    def _push_users(self):
        with self._lock:
            users = list(self._clients.values())
        self._broadcast(MF.users(users))


if __name__ == "__main__":
    server = Server()
    if not server.start():
        raise SystemExit(f"Server failed to start: {server.last_error or 'unknown error'}")
    print(f"Server listening on 0.0.0.0:{server.port}")
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        server.stop()
