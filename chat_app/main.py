"""
main.py - Entry point.

Supports both:
    python -m chat_app.main
and:
    python chat_app/main.py
"""

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chat_app.app import App
else:
    from .app import App

if __name__ == "__main__":
    App().run()
