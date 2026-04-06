"""Reusable UI building blocks."""

import tkinter as tk
from tkinter import ttk

from ..core.config import Theme


class Bubbles:
    """Renders individual message rows directly into a parent Frame."""

    @staticmethod
    def system(parent: tk.Frame, text: str):
        frame = tk.Frame(parent, bg=Theme.BG_DARK)
        frame.pack(fill="x", padx=20, pady=2)
        tk.Label(
            frame,
            text=f"-- {text} --",
            font=("Helvetica", 9, "italic"),
            bg=Theme.BG_DARK,
            fg=Theme.MUTED,
        ).pack()

    @staticmethod
    def chat(
        parent: tk.Frame,
        username: str,
        text: str,
        ts: str,
        is_self: bool,
        compact: bool = False,
        on_delete=None,
    ):
        avatar_width = 3
        bubble_color = Theme.BUBBLE_ME if is_self else Theme.BUBBLE_OTHER
        parts = username.split()
        initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else username[:2].upper()
        avatar_bg = Theme.BUBBLE_ME if is_self else "#30363D"

        row = tk.Frame(parent, bg=Theme.BG_DARK)
        row.pack(fill="x", padx=16, pady=(1 if compact else 4))

        inner = tk.Frame(row, bg=Theme.BG_DARK)
        inner.pack(side="right" if is_self else "left")

        if not is_self:
            if compact:
                tk.Label(inner, text="", bg=Theme.BG_DARK, width=avatar_width, pady=0).pack(
                    side="left", padx=(0, 6)
                )
            else:
                tk.Label(
                    inner,
                    text=initials,
                    font=("Helvetica", 9, "bold"),
                    bg=avatar_bg,
                    fg=Theme.TEXT,
                    width=avatar_width,
                    pady=4,
                ).pack(side="left", anchor="n", padx=(0, 6))

        column = tk.Frame(inner, bg=Theme.BG_DARK)
        column.pack(side="left" if not is_self else "right")

        if not compact:
            meta = tk.Frame(column, bg=Theme.BG_DARK)
            meta.pack(fill="x")
            if not is_self:
                tk.Label(
                    meta,
                    text=username,
                    font=("Helvetica", 9, "bold"),
                    bg=Theme.BG_DARK,
                    fg=Theme.ACCENT,
                ).pack(side="left")
            tk.Label(
                meta,
                text=f"  {ts}",
                font=Theme.T_MICRO,
                bg=Theme.BG_DARK,
                fg=Theme.MUTED,
            ).pack(side="left" if not is_self else "right")

        bubble = tk.Frame(column, bg=bubble_color)
        bubble.pack(anchor="e" if is_self else "w", pady=1)
        tk.Label(
            bubble,
            text=text,
            font=Theme.T_BODY,
            bg=bubble_color,
            fg=Theme.TEXT,
            wraplength=360,
            justify="left",
            padx=12,
            pady=7,
        ).pack()
        if on_delete and is_self:
            delete_row = tk.Frame(column, bg=Theme.BG_DARK)
            delete_row.pack(fill="x", pady=(2, 0))
            tk.Label(
                delete_row,
                text="Delete",
                font=Theme.T_MICRO,
                bg=Theme.BG_DARK,
                fg=Theme.DANGER,
                cursor="hand2",
            ).pack(side="right")
            delete_row.winfo_children()[-1].bind("<Button-1>", lambda _e: on_delete())

        if is_self:
            if compact:
                tk.Label(inner, text="", bg=Theme.BG_DARK, width=avatar_width, pady=0).pack(
                    side="right", padx=(6, 0)
                )
            else:
                tk.Label(
                    inner,
                    text=initials,
                    font=("Helvetica", 9, "bold"),
                    bg=avatar_bg,
                    fg=Theme.TEXT,
                    width=avatar_width,
                    pady=4,
                ).pack(side="right", anchor="n", padx=(6, 0))


class ScrollCanvas:
    """A Canvas + Scrollbar combo with an inner Frame for widget children."""

    def __init__(self, parent: tk.Widget):
        outer = tk.Frame(parent, bg=Theme.BG_DARK)
        outer.pack(fill="both", expand=True)

        self._c = tk.Canvas(outer, bg=Theme.BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self._c.yview)
        self._c.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._c.pack(side="left", fill="both", expand=True)

        self.frame = tk.Frame(self._c, bg=Theme.BG_DARK)
        self._win = self._c.create_window((0, 0), window=self.frame, anchor="nw")

        self.frame.bind(
            "<Configure>",
            lambda _: self._c.configure(scrollregion=self._c.bbox("all")),
        )
        self._c.bind(
            "<Configure>",
            lambda e: self._c.itemconfig(self._win, width=e.width),
        )
        self._c.bind(
            "<MouseWheel>",
            lambda e: self._c.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        self._c.bind("<Button-4>", lambda _: self._c.yview_scroll(-1, "units"))
        self._c.bind("<Button-5>", lambda _: self._c.yview_scroll(1, "units"))

    def to_bottom(self):
        self._c.after(60, lambda: self._c.yview_moveto(1.0))

    def clear(self):
        for widget in self.frame.winfo_children():
            widget.destroy()


class BaseWindow:
    """Common window setup: title, bg, centering, ttk style, build hook."""

    def __init__(
        self,
        root: tk.Tk,
        title: str,
        width: int,
        height: int,
        resizable: bool = True,
    ):
        self.root = root
        root.title(title)
        root.configure(bg=Theme.BG_DARK)
        if not resizable:
            root.resizable(False, False)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")
        Theme.setup_ttk(ttk.Style(root))
        self._build()

    def _build(self):
        raise NotImplementedError("Subclasses must implement _build()")
