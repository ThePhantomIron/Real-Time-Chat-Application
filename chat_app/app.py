"""
app.py — Application root.

Manages the single Tk root window and transitions between
LoginWindow and ChatWindow.
"""

import tkinter as tk

from .core.config import Theme
from .core.models import UserSession
from .network.client import Client
from .ui.chat_window_network import ChatWindow
from .ui.login_window_network import LoginWindow


class App:
    """Top-level controller: owns the Tk root and orchestrates window transitions."""

    def __init__(self):
        self._root = tk.Tk()
        self._root.configure(bg=Theme.BG_DARK)
        self._show_login()

    def run(self):
        self._root.mainloop()

    # ── Window transitions ────────────────────────────────────────────────────

    def _show_login(self):
        self._clear()
        LoginWindow(self._root, on_login=self._on_login)

    def _on_login(self, session: UserSession, client: Client):
        self._clear()
        ChatWindow(self._root, session, client, on_logout=self._on_logout)

    def _on_logout(self):
        self._show_login()

    def _clear(self):
        for widget in self._root.winfo_children():
            widget.destroy()
