"""App-wide constants and theme definitions."""

import os


class Config:
    DEFAULT_SERVER_HOST = "127.0.0.1"
    SERVER_BIND_HOST = "0.0.0.0"
    PORT = 9090
    BUFFER = 4096
    MAX_MSG = 500
    HISTORY_LOAD = 50
    DB_PATH = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chat.db")
    )
    DEFAULT_CHANNELS = ["general", "random", "announcements", "off-topic"]


class Theme:
    BG_DARK, BG_MID, BG_LIGHT = "#0D1117", "#161B22", "#21262D"
    ACCENT, ACCENT2 = "#00D4AA", "#7EE787"
    BUBBLE_ME, BUBBLE_OTHER = "#1F6FEB", "#21262D"
    TEXT, MUTED, BORDER = "#E6EDF3", "#8B949E", "#30363D"
    ONLINE, DANGER, WARN = "#3FB950", "#F85149", "#D29922"
    DM_ACCENT = "#A371F7"

    T_TITLE = ("Helvetica", 13, "bold")
    T_BODY = ("Helvetica", 11)
    T_SMALL = ("Helvetica", 9)
    T_MICRO = ("Helvetica", 8)
    T_INPUT = ("Helvetica", 12)
    T_BTN = ("Helvetica", 10, "bold")

    @staticmethod
    def setup_ttk(style):
        style.theme_use("clam")
        style.configure(
            "Vertical.TScrollbar",
            background=Theme.BG_LIGHT,
            troughcolor=Theme.BG_DARK,
            arrowcolor=Theme.MUTED,
            bordercolor=Theme.BG_DARK,
        )
