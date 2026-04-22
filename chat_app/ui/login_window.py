"""Authentication screen (login and register views)."""

import queue
import threading
import time
from typing import Callable

import tkinter as tk

from ..core.config import Theme
from ..core.models import UserSession
from ..network.client import Client
from ..server import Server
from .widgets import BaseWindow


class LoginWindow(BaseWindow):
    """Presents login and register forms and transitions into the chat app."""

    _SPINNER = ["◐", "◓", "◑", "◒"]

    def __init__(self, root: tk.Tk, on_login: Callable):
        self._on_login = on_login
        self._alive = True
        self._return_bind_id = None
        self._mode = tk.StringVar(value="login")
        self._user_var = tk.StringVar()
        self._pw_var = tk.StringVar()
        self._pw2_var = tk.StringVar()
        self._status_lbl = None
        self._pw2_row = None
        self._btn = None
        self._alt_btn = None
        self._spin_job = None
        self._spinner = None
        self._tab_login = None
        self._tab_reg = None
        self._si = 0
        super().__init__(root, "Chat - Sign In", 400, 560, resizable=False)
        self._return_bind_id = root.bind("<Return>", self._on_return)

    def _on_return(self, _event=None):
        self._submit()

    @staticmethod
    def _widget_exists(widget) -> bool:
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _view_alive(self) -> bool:
        return self._alive and self._widget_exists(self._status_lbl)

    def _queue_ui(self, callback):
        if not self._widget_exists(self.root):
            return
        try:
            self.root.after(0, callback)
        except tk.TclError:
            pass

    def _teardown(self):
        if not self._alive:
            return
        self._alive = False
        if self._return_bind_id and self._widget_exists(self.root):
            try:
                self.root.unbind("<Return>", self._return_bind_id)
            except tk.TclError:
                pass
            self._return_bind_id = None
        self._stop_spin()

    def _build(self):
        hero = tk.Frame(self.root, bg=Theme.BG_DARK)
        hero.pack(pady=(36, 0))
        tk.Label(
            hero,
            text="💬",
            font=("Helvetica", 48),
            bg=Theme.BG_DARK,
            fg=Theme.ACCENT,
        ).pack()
        tk.Label(
            hero,
            text="Chat",
            font=("Helvetica", 26, "bold"),
            bg=Theme.BG_DARK,
            fg=Theme.TEXT,
        ).pack()
        tk.Label(
            hero,
            text="localhost  ·  SQLite",
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
        self._mk_field(inner, "Password", self._pw_var, show="●")

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
            show="●",
        )
        self._pw2_entry.pack(fill="x")
        self._pw2_entry.bind("<FocusIn>", lambda _: pw2_wrap.config(highlightbackground=Theme.ACCENT))
        self._pw2_entry.bind("<FocusOut>", lambda _: pw2_wrap.config(highlightbackground=Theme.BORDER))

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

        threading.Thread(target=lambda: Server().start(), daemon=True).start()

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

    def _submit(self):
        if not self._view_alive():
            return
        user = self._user_var.get().strip()
        pw = self._pw_var.get()
        mode = self._mode.get()

        if not user or not pw:
            self._set_status("Please fill in all fields.", Theme.DANGER)
            return
        if mode == "register" and pw != self._pw2_var.get():
            self._set_status("Passwords do not match.", Theme.DANGER)
            return

        self._set_status("Connecting...", Theme.WARN)
        self._btn.config(state="disabled")
        self._alt_btn.config(state="disabled")
        self._start_spin()

        def work():
            time.sleep(0.35)

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

            if not client.connect(mode, pw):
                self._queue_ui(lambda: self._fail("Cannot reach server."))
                return

            try:
                msg = auth_q.get(timeout=6)
            except Exception:
                client.disconnect()
                self._queue_ui(lambda: self._fail("Server did not respond."))
                return

            if msg.get("type") == "auth_ok":
                canonical = msg["username"]
                self._queue_ui(lambda c=canonical, cl=client: self._success(c, cl))
            else:
                reason = msg.get("reason", "Authentication failed.")
                client.disconnect()
                self._queue_ui(lambda r=reason: self._fail(r))

        threading.Thread(target=work, daemon=True).start()

    def _success(self, canonical: str, client: Client):
        if not self._view_alive():
            return
        self._stop_spin()
        self._set_status(f"Welcome, {canonical}!", Theme.ONLINE)
        self._teardown()
        self._on_login(UserSession(canonical), client)

    def _fail(self, reason: str):
        if not self._view_alive():
            return
        self._stop_spin()
        if self._widget_exists(self._btn):
            self._btn.config(state="normal")
        if self._widget_exists(self._alt_btn):
            self._alt_btn.config(state="normal")
        self._set_status(reason, Theme.DANGER)

    def _start_spin(self):
        self._si = 0
        self._tick()

    def _tick(self):
        if not self._view_alive():
            self._spin_job = None
            return
        if self._widget_exists(self._spinner):
            self._spinner.config(text=self._SPINNER[self._si % len(self._SPINNER)])
        self._si += 1
        try:
            self._spin_job = self.root.after(150, self._tick)
        except tk.TclError:
            self._spin_job = None

    def _stop_spin(self):
        if self._spin_job:
            try:
                self.root.after_cancel(self._spin_job)
            except tk.TclError:
                pass
            self._spin_job = None
        if self._widget_exists(self._spinner):
            self._spinner.config(text="")

    def _set_status(self, text: str, color: str):
        if self._widget_exists(self._status_lbl):
            self._status_lbl.config(text=text, fg=color)
