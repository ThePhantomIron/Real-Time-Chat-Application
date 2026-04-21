"""Authentication screen for logging in, registering, and joining a host."""

import queue
import socket
import threading
import time
from typing import Callable

import tkinter as tk

from ..core.config import Config, Theme
from ..core.models import UserSession
from ..network.client import Client
from ..server import Server
from .widgets import BaseWindow

_LOCAL_SERVER = None
_LOCAL_SERVER_LOCK = threading.Lock()


def ensure_local_server() -> tuple[bool, str]:
    """Start the local server once and reuse it across logins."""

    global _LOCAL_SERVER
    with _LOCAL_SERVER_LOCK:
        if _LOCAL_SERVER and _LOCAL_SERVER.is_running:
            return True, ""
        _LOCAL_SERVER = Server()
        if _LOCAL_SERVER.start():
            return True, ""
        return False, _LOCAL_SERVER.last_error or "Server failed to start."


def get_local_ip() -> str:
    """Best-effort LAN IP discovery for the host hint."""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return Config.DEFAULT_SERVER_HOST


class LoginWindow(BaseWindow):
    """Presents login and register forms and transitions into the chat app."""

    _SPINNER = ["|", "/", "-", "\\"]

    def __init__(self, root: tk.Tk, on_login: Callable):
        self._on_login = on_login
        self._mode = tk.StringVar(value="login")
        self._user_var = tk.StringVar()
        self._pw_var = tk.StringVar()
        self._pw2_var = tk.StringVar()
        self._host_var = tk.StringVar(value=Config.DEFAULT_SERVER_HOST)
        self._host_local_var = tk.BooleanVar(value=False)
        self._status_lbl = None
        self._server_lbl = None
        self._pw2_row = None
        self._btn = None
        self._alt_btn = None
        self._spin_job = None
        self._spinner = None
        self._tab_login = None
        self._tab_reg = None
        self._si = 0
        super().__init__(root, "Chat - Sign In", 420, 680, resizable=False)
        root.bind("<Return>", lambda _: self._submit())

    def _build(self):
        hero = tk.Frame(self.root, bg=Theme.BG_DARK)
        hero.pack(pady=(36, 0))
        tk.Label(
            hero,
            text="Chat",
            font=("Helvetica", 26, "bold"),
            bg=Theme.BG_DARK,
            fg=Theme.TEXT,
        ).pack()
        tk.Label(
            hero,
            text="Shared LAN chat over TCP",
            font=Theme.T_SMALL,
            bg=Theme.BG_DARK,
            fg=Theme.MUTED,
        ).pack(pady=(2, 0))

        card = tk.Frame(
            self.root,
            bg=Theme.BG_MID,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        card.pack(padx=40, pady=22, fill="x")
        inner = tk.Frame(card, bg=Theme.BG_MID)
        inner.pack(padx=28, pady=24, fill="x")

        tabs = tk.Frame(inner, bg=Theme.BG_MID)
        tabs.pack(fill="x", pady=(0, 18))
        self._tab_login = tk.Button(
            tabs,
            text="Log In",
            font=Theme.T_BTN,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self._set_mode("login"),
        )
        self._tab_reg = tk.Button(
            tabs,
            text="Register",
            font=Theme.T_BTN,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self._set_mode("register"),
        )
        self._tab_login.pack(side="left", padx=(0, 8))
        self._tab_reg.pack(side="left")
        self._update_tabs()

        self._mk_field(inner, "Username", self._user_var, show=None, focus=True)
        self._mk_field(inner, "Password", self._pw_var, show="*")

        self._pw2_row = tk.Frame(inner, bg=Theme.BG_MID)
        tk.Label(
            self._pw2_row,
            text="Confirm Password",
            font=Theme.T_MICRO,
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
            anchor="w",
        ).pack(fill="x")
        pw2_wrap = tk.Frame(
            self._pw2_row,
            bg=Theme.BG_LIGHT,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        pw2_wrap.pack(fill="x", pady=(2, 10))
        self._pw2_entry = tk.Entry(
            pw2_wrap,
            textvariable=self._pw2_var,
            font=Theme.T_INPUT,
            bg=Theme.BG_LIGHT,
            fg=Theme.TEXT,
            insertbackground=Theme.ACCENT,
            relief="flat",
            bd=8,
            show="*",
        )
        self._pw2_entry.pack(fill="x")
        self._pw2_entry.bind(
            "<FocusIn>",
            lambda _: pw2_wrap.config(highlightbackground=Theme.ACCENT),
        )
        self._pw2_entry.bind(
            "<FocusOut>",
            lambda _: pw2_wrap.config(highlightbackground=Theme.BORDER),
        )

        self._mk_field(inner, "Server Address", self._host_var, show=None)

        tk.Checkbutton(
            inner,
            text="Host chat on this PC",
            variable=self._host_local_var,
            command=self._refresh_host_details,
            font=Theme.T_SMALL,
            bg=Theme.BG_MID,
            fg=Theme.TEXT,
            activebackground=Theme.BG_MID,
            activeforeground=Theme.TEXT,
            selectcolor=Theme.BG_LIGHT,
            anchor="w",
            relief="flat",
            bd=0,
        ).pack(fill="x", pady=(4, 0))

        self._server_lbl = tk.Label(
            inner,
            text="",
            font=Theme.T_MICRO,
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
            justify="left",
            anchor="w",
        )
        self._server_lbl.pack(fill="x", pady=(6, 12))
        self._refresh_host_details()

        self._btn = tk.Button(
            inner,
            text="Log In",
            font=Theme.T_BTN,
            bg=Theme.ACCENT,
            fg="#0D1117",
            activebackground=Theme.ACCENT2,
            activeforeground="#0D1117",
            relief="flat",
            cursor="hand2",
            pady=9,
            bd=0,
            command=self._submit,
        )
        self._btn.pack(fill="x")

        self._alt_btn = tk.Button(
            inner,
            text="Register",
            font=Theme.T_BTN,
            bg=Theme.BG_LIGHT,
            fg=Theme.TEXT,
            activebackground=Theme.BG_LIGHT,
            activeforeground=Theme.TEXT,
            relief="flat",
            cursor="hand2",
            pady=9,
            bd=0,
            command=self._toggle_auth_mode,
        )
        self._alt_btn.pack(fill="x", pady=(8, 0))

        self._status_lbl = tk.Label(
            self.root,
            text="",
            font=Theme.T_SMALL,
            bg=Theme.BG_DARK,
            fg=Theme.MUTED,
        )
        self._status_lbl.pack(pady=(10, 0))
        self._spinner = tk.Label(
            self.root,
            text="",
            font=("Helvetica", 18),
            bg=Theme.BG_DARK,
            fg=Theme.ACCENT,
        )
        self._spinner.pack()

    def _mk_field(self, parent, label: str, var, show, focus: bool = False):
        frame = tk.Frame(parent, bg=Theme.BG_MID)
        frame.pack(fill="x")
        tk.Label(
            frame,
            text=label,
            font=Theme.T_MICRO,
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
            anchor="w",
        ).pack(fill="x")
        wrap = tk.Frame(
            frame,
            bg=Theme.BG_LIGHT,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        wrap.pack(fill="x", pady=(2, 10))
        kwargs = {} if show is None else {"show": show}
        entry = tk.Entry(
            wrap,
            textvariable=var,
            font=Theme.T_INPUT,
            bg=Theme.BG_LIGHT,
            fg=Theme.TEXT,
            insertbackground=Theme.ACCENT,
            relief="flat",
            bd=8,
            **kwargs,
        )
        entry.pack(fill="x")
        entry.bind("<FocusIn>", lambda _: wrap.config(highlightbackground=Theme.ACCENT))
        entry.bind("<FocusOut>", lambda _: wrap.config(highlightbackground=Theme.BORDER))
        if focus:
            entry.focus()
        return entry

    def _set_mode(self, mode: str):
        self._mode.set(mode)
        self._update_tabs()
        if mode == "register":
            self._pw2_row.pack(fill="x", before=self._btn)
            self._btn.config(text="Create Account")
            self._alt_btn.config(text="Back to Login")
        else:
            self._pw2_row.pack_forget()
            self._btn.config(text="Log In")
            self._alt_btn.config(text="Register")

    def _toggle_auth_mode(self):
        self._set_mode("register" if self._mode.get() == "login" else "login")

    def _update_tabs(self):
        mode = self._mode.get()
        self._tab_login.config(
            bg=Theme.ACCENT if mode == "login" else Theme.BG_MID,
            fg="#0D1117" if mode == "login" else Theme.MUTED,
        )
        self._tab_reg.config(
            bg=Theme.ACCENT if mode == "register" else Theme.BG_MID,
            fg="#0D1117" if mode == "register" else Theme.MUTED,
        )

    def _refresh_host_details(self):
        if not self._server_lbl:
            return
        if self._host_local_var.get():
            local_ip = get_local_ip()
            self._server_lbl.config(
                text=(
                    f"This PC will host on port {Config.PORT}.\n"
                    f"Other PCs can join using: {local_ip}:{Config.PORT}"
                ),
                fg=Theme.ACCENT,
            )
        else:
            self._server_lbl.config(
                text="Enter the host PC IP address to join the shared chat.",
                fg=Theme.MUTED,
            )

    def _submit(self):
        user = self._user_var.get().strip()
        password = self._pw_var.get()
        mode = self._mode.get()
        requested_host = self._host_var.get().strip() or Config.DEFAULT_SERVER_HOST
        connect_host = Config.DEFAULT_SERVER_HOST if self._host_local_var.get() else requested_host

        if not user or not password:
            self._set_status("Please fill in all fields.", Theme.DANGER)
            return
        if mode == "register" and password != self._pw2_var.get():
            self._set_status("Passwords do not match.", Theme.DANGER)
            return

        self._set_status("Connecting...", Theme.WARN)
        self._btn.config(state="disabled")
        self._alt_btn.config(state="disabled")
        self._start_spin()

        def work():
            time.sleep(0.2)

            if self._host_local_var.get():
                ok, reason = ensure_local_server()
                if not ok:
                    self.root.after(0, lambda r=reason: self._fail(r))
                    return

            auth_q = queue.Queue()
            buf_q = queue.Queue()

            def on_msg(msg):
                buf_q.put(msg)
                if msg.get("type") in ("auth_ok", "auth_fail"):
                    auth_q.put(msg)

            def on_err(err):
                auth_q.put({"type": "auth_fail", "reason": str(err)})

            client = Client(user, on_msg=on_msg, on_err=on_err)
            client._buf_q = buf_q

            if not client.connect(mode, password, host=connect_host):
                self.root.after(
                    0,
                    lambda: self._fail(
                        f"Cannot reach server at {connect_host}:{Config.PORT}."
                    ),
                )
                return

            try:
                msg = auth_q.get(timeout=6)
            except Exception:
                client.disconnect()
                self.root.after(0, lambda: self._fail("Server did not respond."))
                return

            if msg.get("type") == "auth_ok":
                canonical = msg["username"]
                self.root.after(
                    0,
                    lambda c=canonical, cl=client: self._success(c, cl),
                )
            else:
                reason = msg.get("reason", "Authentication failed.")
                client.disconnect()
                self.root.after(0, lambda r=reason: self._fail(r))

        threading.Thread(target=work, daemon=True).start()

    def _success(self, canonical: str, client: Client):
        self._stop_spin()
        self._set_status(
            f"Connected to {client.server_host}:{client.server_port} as {canonical}.",
            Theme.ONLINE,
        )
        self._on_login(UserSession(canonical), client)

    def _fail(self, reason: str):
        self._stop_spin()
        self._btn.config(state="normal")
        self._alt_btn.config(state="normal")
        self._set_status(reason, Theme.DANGER)

    def _start_spin(self):
        self._si = 0
        self._tick()

    def _tick(self):
        if self._spinner:
            self._spinner.config(text=self._SPINNER[self._si % len(self._SPINNER)])
        self._si += 1
        self._spin_job = self.root.after(150, self._tick)

    def _stop_spin(self):
        if self._spin_job:
            self.root.after_cancel(self._spin_job)
            self._spin_job = None
        if self._spinner:
            self._spinner.config(text="")

    def _set_status(self, text: str, color: str):
        if self._status_lbl:
            self._status_lbl.config(text=text, fg=color)
