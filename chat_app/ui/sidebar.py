"""Left-hand navigation panel.

Shows channels, DM peers, and online member list.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Callable

from ..core.config import Theme
from ..core.models import ChannelMgr


class Sidebar:
    """
    Builds and manages the left sidebar:
      - Channel list (with add / rename / remove actions)
      - DM peer list
      - Online members list
    """

    def __init__(
        self,
        parent: tk.Widget,
        cm: ChannelMgr,
        on_switch: Callable[[str], None],
        on_rename: Callable[[str, str], None],
        on_add: Callable[[str], None],
        on_remove: Callable[[str], None],
        on_dm: Callable[[str], None],
        on_dm_remove: Callable[[str], None],
    ):
        self._cm = cm
        self._sw = on_switch
        self._ren = on_rename
        self._add = on_add
        self._rem = on_remove
        self._on_dm = on_dm
        self._on_dm_remove = on_dm_remove
        self._mem = None
        self._olbl = None
        self._chbx = None
        self._dmbx = None

        self.frame = tk.Frame(
            parent,
            bg=Theme.BG_MID,
            width=190,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        self.frame.pack(side="left", fill="y")
        self.frame.pack_propagate(False)
        self._build()

    def _build(self):
        header = tk.Frame(self.frame, bg=Theme.BG_MID)
        header.pack(fill="x", padx=10, pady=(14, 4))
        tk.Label(
            header,
            text="GROUPS",
            font=("Helvetica", 8, "bold"),
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
        ).pack(side="left")
        tk.Button(
            header,
            text="+ Group",
            font=("Helvetica", 11, "bold"),
            bg=Theme.BG_MID,
            fg=Theme.ACCENT,
            activebackground=Theme.BG_LIGHT,
            relief="flat",
            cursor="hand2",
            bd=0,
            command=self._ask_add,
        ).pack(side="right")

        self._chbx = tk.Frame(self.frame, bg=Theme.BG_MID)
        self._chbx.pack(fill="x")
        self._render_channels()

        tk.Label(
            self.frame,
            text="DIRECT MESSAGES",
            font=("Helvetica", 8, "bold"),
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(18, 4))
        self._dmbx = tk.Frame(self.frame, bg=Theme.BG_MID)
        self._dmbx.pack(fill="x")

        tk.Label(
            self.frame,
            text="MEMBERS",
            font=("Helvetica", 8, "bold"),
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(18, 4))
        self._mem = tk.Frame(self.frame, bg=Theme.BG_MID)
        self._mem.pack(fill="x", padx=8)
        self._olbl = tk.Label(
            self.frame,
            text="0 online",
            font=Theme.T_MICRO,
            bg=Theme.BG_MID,
            fg=Theme.MUTED,
            anchor="w",
        )
        self._olbl.pack(fill="x", padx=14, pady=(4, 0))

    def _render_channels(self):
        for widget in self._chbx.winfo_children():
            widget.destroy()
        for channel in self._cm.channels:
            self._channel_row(channel)

    def _render_dms(self):
        for widget in self._dmbx.winfo_children():
            widget.destroy()
        for peer in self._cm.dm_peers:
            key = self._cm.dm_key_for(peer)
            active = key == self._cm.active
            bg = Theme.DM_ACCENT if active else Theme.BG_MID
            fg = "#0D1117" if active else Theme.MUTED

            row = tk.Frame(self._dmbx, bg=bg, cursor="hand2")
            row.pack(fill="x", padx=8, pady=1)
            label = tk.Label(
                row,
                text=f"@ {peer}",
                font=("Helvetica", 10),
                bg=bg,
                fg=fg,
                anchor="w",
                pady=5,
            )
            label.pack(side="left", fill="x", expand=True, padx=8)

            actions = tk.Frame(row, bg=bg)
            delete = tk.Label(
                actions,
                text="X",
                font=("Helvetica", 10, "bold"),
                bg=bg,
                fg=fg,
                cursor="hand2",
            )
            delete.pack(side="left")
            actions.pack_forget()

            def on_enter(_event, target=row, original=bg, action_box=actions):
                hover = Theme.BG_LIGHT if original != Theme.DM_ACCENT else Theme.DM_ACCENT
                target.config(bg=hover)
                for child in target.winfo_children():
                    try:
                        child.config(bg=hover)
                    except Exception:
                        pass
                action_box.pack(side="right", padx=4)

            def on_leave(_event, target=row, original=bg, action_box=actions):
                target.config(bg=original)
                for child in target.winfo_children():
                    try:
                        child.config(bg=original)
                    except Exception:
                        pass
                action_box.pack_forget()

            for widget in (row, label, actions, delete):
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)
            for widget in (row, label):
                widget.bind("<Button-1>", lambda _, p=peer: self._on_dm(p))
            delete.bind("<Button-1>", lambda _, p=peer: self._ask_remove_dm(p))

    def _channel_row(self, channel: str):
        active = channel == self._cm.active
        bg = Theme.ACCENT if active else Theme.BG_MID
        fg = "#0D1117" if active else Theme.MUTED

        row = tk.Frame(self._chbx, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=8, pady=1)
        label = tk.Label(
            row,
            text=f"# {channel}",
            font=("Helvetica", 10),
            bg=bg,
            fg=fg,
            anchor="w",
            pady=5,
        )
        label.pack(side="left", fill="x", expand=True, padx=8)

        actions = tk.Frame(row, bg=bg)
        rename = tk.Label(actions, text="R", font=("Helvetica", 9), bg=bg, fg=fg, cursor="hand2")
        delete = tk.Label(actions, text="X", font=("Helvetica", 10, "bold"), bg=bg, fg=fg, cursor="hand2")
        rename.pack(side="left", padx=2)
        delete.pack(side="left")
        actions.pack_forget()

        def recolor(widget, color):
            try:
                widget.config(bg=color)
            except Exception:
                pass
            for child in widget.winfo_children():
                recolor(child, color)

        def on_enter(_event, target=row, action_box=actions, original=bg):
            hover = Theme.BG_LIGHT if original != Theme.ACCENT else Theme.ACCENT
            recolor(target, hover)
            action_box.pack(side="right", padx=4)

        def on_leave(_event, target=row, action_box=actions, original=bg):
            recolor(target, original)
            action_box.pack_forget()

        for widget in (row, label, actions, rename, delete):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
        for widget in (row, label):
            widget.bind("<Button-1>", lambda _, c=channel: self._sw(c))
        rename.bind("<Button-1>", lambda _, c=channel: self._ask_rename(c))
        delete.bind("<Button-1>", lambda _, c=channel: self._ask_remove(c))

    def _ask_add(self):
        name = simpledialog.askstring("Create group", "Group name:", parent=self.frame)
        if name:
            self._add(name)

    def _ask_rename(self, channel: str):
        name = simpledialog.askstring(
            "Rename",
            f"New name for #{channel}:",
            initialvalue=channel,
            parent=self.frame,
        )
        if name:
            self._ren(channel, name)

    def _ask_remove(self, channel: str):
        if messagebox.askyesno("Remove", f"Remove #{channel}?", parent=self.frame):
            self._rem(channel)

    def _ask_remove_dm(self, peer: str):
        if messagebox.askyesno("Remove", f"Delete private chat with {peer}?", parent=self.frame):
            self._on_dm_remove(peer)

    def refresh(self):
        self._render_channels()
        self._render_dms()

    def update_members(self, users: list[str], my_name: str = ""):
        for widget in self._mem.winfo_children():
            widget.destroy()
        for user in sorted(users):
            if user == my_name:
                continue
            frame = tk.Frame(self._mem, bg=Theme.BG_MID)
            frame.pack(fill="x", padx=4, pady=1)
            label = tk.Label(
                frame,
                text=f"* {user}",
                font=("Helvetica", 10),
                bg=Theme.BG_MID,
                fg=Theme.ONLINE,
                anchor="w",
                pady=3,
                cursor="hand2",
            )
            label.pack(fill="x", padx=6)
            label.bind("<Button-1>", lambda _, peer=user: self._on_dm(peer))
            label.bind("<Enter>", lambda _, w=label: w.config(fg=Theme.DM_ACCENT))
            label.bind("<Leave>", lambda _, w=label: w.config(fg=Theme.ONLINE))

        count = len([u for u in users if u != my_name])
        self._olbl.config(text=f"{count} online")
