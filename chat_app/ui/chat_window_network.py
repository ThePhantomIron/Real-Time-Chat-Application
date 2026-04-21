"""Main chat interface shown after successful login."""

import re
import tkinter as tk
from tkinter import messagebox

from ..core.config import Config, Theme
from ..core.models import ChannelMgr, UserSession
from ..network.client import Client
from .sidebar import Sidebar
from .widgets import BaseWindow, Bubbles, ScrollCanvas


class ChatWindow(BaseWindow):
    """Full chat UI for messages, channels, and direct messages."""

    def __init__(self, root: tk.Tk, session: UserSession, client: Client, on_logout=None):
        self._session = session
        self._client = client
        self._on_logout = on_logout
        self._cm = None
        self._sidebar = None
        self._canvas = None
        self._msg_var = None
        self._entry = None
        self._online = set()
        self._dot = None
        self._connlbl = None
        self._chlbl = None
        self._dm_badge = None
        self._pending = []
        self._cm_ready = False

        client._on_msg = lambda m: root.after(0, lambda msg=m: self._handle(msg))
        client._on_err = lambda _: root.after(
            0,
            lambda: self._status("Disconnected", Theme.DANGER),
        )

        buf_q = getattr(client, "_buf_q", None)
        if buf_q:
            while not buf_q.empty():
                try:
                    msg = buf_q.get_nowait()
                    root.after(0, lambda queued=msg: self._handle(queued))
                except Exception:
                    break

        super().__init__(root, f"Chat - {session.name}", 900, 660)
        root.minsize(680, 480)
        root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        self._topbar()
        self._body = tk.Frame(self.root, bg=Theme.BG_DARK)
        self._body.pack(fill="both", expand=True)
        self._loading = tk.Label(
            self._body,
            text="Loading history...",
            font=Theme.T_BODY,
            bg=Theme.BG_DARK,
            fg=Theme.MUTED,
        )
        self._loading.pack(expand=True)
        self._status(
            f"Connected to {self._client.server_host}:{self._client.server_port}",
            Theme.ONLINE,
        )

    def _finish_build(self, channels: list[str]):
        self._cm = ChannelMgr(channels)
        self._loading.destroy()

        self._sidebar = Sidebar(
            self._body,
            self._cm,
            on_switch=self._switch,
            on_rename=self._rename,
            on_add=self._add_ch,
            on_remove=self._remove_ch,
            on_dm=self._open_dm,
            on_dm_remove=self._remove_dm,
        )
        right = tk.Frame(self._body, bg=Theme.BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        self._chbar(right)
        self._canvas = ScrollCanvas(right)
        self._inputbar(right)

        Bubbles.system(self._canvas.frame, f"Welcome back, {self._session.name}.")
        Bubbles.system(self._canvas.frame, f"You are in #{self._cm.active}.")

        self._cm_ready = True
        for msg in self._pending:
            self._handle(msg)
        self._pending.clear()

    def _topbar(self):
        bar = tk.Frame(
            self.root,
            bg=Theme.BG_MID,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        bar.pack(fill="x")
        tk.Label(
            bar,
            text="Chat",
            font=Theme.T_TITLE,
            bg=Theme.BG_MID,
            fg=Theme.ACCENT,
        ).pack(side="left", padx=16, pady=10)

        badge = tk.Frame(bar, bg=Theme.BG_MID)
        badge.pack(side="right", padx=16, pady=8)
        tk.Label(
            badge,
            text=self._session.initials,
            font=("Helvetica", 9, "bold"),
            bg=Theme.ACCENT,
            fg="#0D1117",
            width=3,
            pady=5,
            padx=2,
        ).pack(side="left", padx=(0, 8))
        info = tk.Frame(badge, bg=Theme.BG_MID)
        info.pack(side="left")
        tk.Label(
            info,
            text=self._session.name,
            font=("Helvetica", 9, "bold"),
            bg=Theme.BG_MID,
            fg=Theme.TEXT,
            anchor="w",
        ).pack(anchor="w")

        tk.Frame(bar, bg=Theme.BORDER, width=1).pack(
            side="right", fill="y", pady=8, padx=(0, 4)
        )

        status = tk.Frame(bar, bg=Theme.BG_MID)
        status.pack(side="right", padx=(0, 12), pady=10)
        self._dot = tk.Label(
            status,
            text="*",
            font=("Helvetica", 11),
            bg=Theme.BG_MID,
            fg=Theme.WARN,
        )
        self._connlbl = tk.Label(
            status,
            text="Connecting...",
            font=Theme.T_SMALL,
            bg=Theme.BG_MID,
            fg=Theme.WARN,
        )
        self._dot.pack(side="left")
        self._connlbl.pack(side="left", padx=(3, 0))

        tk.Button(
            bar,
            text="Logout",
            font=Theme.T_BTN,
            bg=Theme.BG_LIGHT,
            fg=Theme.TEXT,
            activebackground=Theme.BG_LIGHT,
            activeforeground=Theme.TEXT,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=5,
            bd=0,
            command=self._logout,
        ).pack(side="right", padx=(0, 8), pady=8)

    def _chbar(self, parent: tk.Widget):
        bar = tk.Frame(
            parent,
            bg=Theme.BG_MID,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        bar.pack(fill="x")
        self._chlbl = tk.Label(
            bar,
            text=f"# {self._cm.active}",
            font=("Helvetica", 11, "bold"),
            bg=Theme.BG_MID,
            fg=Theme.TEXT,
        )
        self._chlbl.pack(side="left", padx=14, pady=8)
        self._dm_badge = tk.Label(
            bar,
            text="Private",
            font=Theme.T_MICRO,
            bg=Theme.BG_MID,
            fg=Theme.DM_ACCENT,
        )

    def _inputbar(self, parent: tk.Widget):
        bar = tk.Frame(
            parent,
            bg=Theme.BG_MID,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        bar.pack(fill="x", side="bottom")
        inner = tk.Frame(bar, bg=Theme.BG_MID)
        inner.pack(fill="x", padx=12, pady=10)

        self._msg_var = tk.StringVar()
        wrap = tk.Frame(
            inner,
            bg=Theme.BG_LIGHT,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        wrap.pack(side="left", fill="x", expand=True)
        self._entry = tk.Entry(
            wrap,
            textvariable=self._msg_var,
            font=Theme.T_INPUT,
            bg=Theme.BG_LIGHT,
            fg=Theme.TEXT,
            insertbackground=Theme.ACCENT,
            relief="flat",
            bd=8,
        )
        self._entry.pack(fill="x")
        self._entry.bind("<Return>", lambda _: self._send())
        self._entry.bind(
            "<FocusIn>",
            lambda _: wrap.config(highlightbackground=Theme.ACCENT),
        )
        self._entry.bind(
            "<FocusOut>",
            lambda _: wrap.config(highlightbackground=Theme.BORDER),
        )
        self._entry.focus()

        tk.Button(
            inner,
            text="Send",
            font=Theme.T_BTN,
            bg=Theme.ACCENT,
            fg="#0D1117",
            activebackground=Theme.ACCENT2,
            activeforeground="#0D1117",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=6,
            bd=0,
            command=self._send,
        ).pack(side="left", padx=(8, 0))

    def _handle(self, msg: dict):
        if not self._cm_ready:
            if msg.get("type") == "channels":
                self._finish_build(msg["channels"])
            else:
                self._pending.append(msg)
            return

        msg_type = msg.get("type")

        if msg_type == "channels":
            self._cm.set_channels(msg["channels"])
            self._sidebar.refresh()
            if not self._cm.is_dm():
                self._chlbl.config(text=f"# {self._cm.active}", fg=Theme.TEXT)
        elif msg_type == "history":
            self._handle_history(msg)
        elif msg_type == "dm_history":
            self._handle_dm_history(msg)
        elif msg_type == "sys":
            self._handle_system(msg)
        elif msg_type == "msg":
            self._handle_msg(msg)
        elif msg_type == "dm":
            self._handle_dm(msg)
        elif msg_type == "dm_deleted":
            self._handle_dm_deleted(msg)
        elif msg_type == "dm_thread_deleted":
            self._handle_dm_thread_deleted(msg)
        elif msg_type == "users":
            self._online = set(msg.get("users", []))
            self._sidebar.update_members(list(self._online), self._session.name)

    def _handle_history(self, msg: dict):
        channel = msg["channel"]
        if channel not in self._cm.channels:
            return

        for item in msg["messages"]:
            self._cm.push(
                channel,
                {
                    "kind": "chat",
                    "id": item.get("id"),
                    "username": item["username"],
                    "text": item["text"],
                    "time": item["time"],
                },
            )
            if channel == self._cm.active:
                self._render_stream(channel)
        if channel == self._cm.active:
            self._canvas.to_bottom()

    def _handle_dm_history(self, msg: dict):
        peer_a, peer_b = msg["peer_a"], msg["peer_b"]
        peer = peer_b if peer_a == self._session.name else peer_a
        key = self._cm.dm_key_for(peer)
        previous = self._cm.active
        if peer not in self._cm.dm_peers:
            self._cm.open_dm(peer)
            self._cm.switch(previous)
            self._sidebar.refresh()
        for item in msg["messages"]:
            self._cm.push(
                key,
                {
                    "kind": "chat",
                    "id": item.get("id"),
                    "username": item["username"],
                    "to": item.get("to"),
                    "text": item["text"],
                    "time": item["time"],
                },
            )
            if self._cm.active == key:
                self._render_stream(key)
        if self._cm.active == key:
            self._canvas.to_bottom()

    def _handle_system(self, msg: dict):
        text = msg["text"]
        active = self._cm.active
        self._cm.push(active, {"kind": "system", "text": text})
        self._render_stream(active)
        self._canvas.to_bottom()

        joined = re.search(r"(?:\S+\s+)?(.+) joined$", text)
        left = re.search(r"(?:\S+\s+)?(.+) left$", text)
        if joined:
            self._online.add(joined.group(1).strip())
            self._sidebar.update_members(list(self._online), self._session.name)
        elif left:
            self._online.discard(left.group(1).strip())
            self._sidebar.update_members(list(self._online), self._session.name)

    def _handle_msg(self, msg: dict):
        channel = msg.get("channel", "general")
        if channel not in self._cm.channels:
            return
        self._cm.push(
            channel,
            {
                "kind": "chat",
                "id": msg.get("id"),
                "username": msg["username"],
                "text": msg["text"],
                "time": msg["time"],
            },
        )
        if channel == self._cm.active:
            self._render_stream(channel)
            self._canvas.to_bottom()

    def _handle_dm(self, msg: dict):
        sender = msg["username"]
        peer = sender if sender != self._session.name else msg["to"]
        key = self._cm.dm_key_for(peer)
        previous = self._cm.active
        if peer not in self._cm.dm_peers:
            self._cm.open_dm(peer)
            self._cm.switch(previous)
            self._sidebar.refresh()
        self._cm.push(
            key,
            {
                "kind": "chat",
                "id": msg.get("id"),
                "username": sender,
                "to": msg.get("to"),
                "text": msg["text"],
                "time": msg["time"],
            },
        )
        if self._cm.active == key:
            self._render_stream(key)
            self._canvas.to_bottom()

    def _handle_dm_deleted(self, msg: dict):
        peer_a, peer_b = msg["peer_a"], msg["peer_b"]
        peer = peer_b if peer_a == self._session.name else peer_a
        key = self._cm.dm_key_for(peer)
        removed = self._cm.remove_message(key, msg["id"])
        if removed and self._cm.active == key:
            self._render_stream(key)
            self._canvas.to_bottom()

    def _handle_dm_thread_deleted(self, msg: dict):
        peer_a, peer_b = msg["peer_a"], msg["peer_b"]
        peer = peer_b if peer_a == self._session.name else peer_a
        removed = self._cm.remove_dm(peer)
        if removed:
            self._sidebar.refresh()
            if self._cm.is_dm():
                self._dm_badge.pack_forget()
            self._switch(self._cm.active)

    def _send(self):
        text = self._msg_var.get().strip()
        if not text:
            return
        if len(text) > Config.MAX_MSG:
            messagebox.showwarning("Too long", f"Max {Config.MAX_MSG} chars.")
            return

        self._msg_var.set("")
        active = self._cm.active
        if self._cm.is_dm(active):
            self._client.send_dm(text, active[len("dm:"):])
        else:
            self._client.send(text, active)

    def _open_dm(self, peer: str):
        if peer == self._session.name:
            return
        key = self._cm.open_dm(peer)
        self._sidebar.refresh()
        self._chlbl.config(text=f"@ {peer}", fg=Theme.DM_ACCENT)
        self._dm_badge.pack(side="left", padx=(0, 8))
        self._render_stream(key)
        self._canvas.to_bottom()

    def _switch(self, channel: str):
        self._cm.switch(channel)
        self._sidebar.refresh()
        if self._cm.is_dm(channel):
            peer = channel[len("dm:"):]
            self._chlbl.config(text=f"@ {peer}", fg=Theme.DM_ACCENT)
            self._dm_badge.pack(side="left", padx=(0, 8))
        else:
            self._chlbl.config(text=f"# {channel}", fg=Theme.TEXT)
            self._dm_badge.pack_forget()
        self._render_stream(channel)
        self._canvas.to_bottom()

    def _add_ch(self, name: str):
        name = name.strip().lower().replace(" ", "-")
        if not self._cm.can_add(name):
            messagebox.showwarning(
                "Cannot create group",
                "Invalid, duplicate, or limit reached.",
            )
            return
        self._client.send_ch_add(name)

    def _rename(self, old: str, new: str):
        new = new.strip().lower().replace(" ", "-")
        if not self._cm.can_rename(old, new):
            messagebox.showwarning("Cannot rename", "Name is invalid or already taken.")
            return
        self._client.send_ch_rename(old, new)

    def _remove_ch(self, channel: str):
        if not self._cm.can_remove(channel):
            messagebox.showwarning("Cannot remove", "Must keep at least one group.")
            return
        self._client.send_ch_remove(channel)

    def _remove_dm(self, peer: str):
        self._client.send_dm_thread_delete(peer)

    def _render_stream(self, key: str):
        self._canvas.clear()
        prev_sender = None
        for item in self._cm.history(key):
            if item.get("kind") == "system":
                Bubbles.system(self._canvas.frame, item["text"])
                prev_sender = None
                continue

            username = item["username"]
            is_self = username == self._session.name
            compact = prev_sender == username
            on_delete = None
            if self._cm.is_dm(key) and is_self and item.get("id") is not None:
                peer = key[len("dm:"):]
                on_delete = lambda msg_id=item["id"], dm_peer=peer: self._delete_dm_message(
                    msg_id,
                    dm_peer,
                )
            Bubbles.chat(
                self._canvas.frame,
                username,
                item["text"],
                item["time"],
                is_self,
                compact,
                on_delete=on_delete,
            )
            prev_sender = username

    def _delete_dm_message(self, msg_id: int, peer: str):
        if not messagebox.askyesno("Delete message", "Delete this private message?"):
            return
        self._client.send_dm_delete(msg_id, peer)

    def _status(self, text: str, color: str):
        if self._dot:
            self._dot.config(fg=color)
            self._connlbl.config(text=text, fg=color)

    def _logout(self):
        if not messagebox.askyesno("Logout", "Log out and return to the sign-in screen?"):
            return
        if self._client:
            self._client.disconnect()
        if callable(self._on_logout):
            self._on_logout()
        else:
            self.root.destroy()

    def _close(self):
        if self._client:
            self._client.disconnect()
        self.root.destroy()
