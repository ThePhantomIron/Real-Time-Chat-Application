"""
models.py — Lightweight domain objects (UserSession, ChannelMgr).
"""


class UserSession:
    """Holds the authenticated user's canonical name and derived UI helpers."""

    def __init__(self, name: str):
        self.name = name

    @property
    def initials(self) -> str:
        parts = self.name.split()
        if len(parts) > 1:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.name[:2].upper()


class ChannelMgr:
    """
    Tracks channels, DM peers, message history functions, and the active view.
    Pure in-memory state — no I/O.
    """

    def __init__(self, channels: list[str]):
        self._chs      = list(channels)
        self._active   = self._chs[0] if self._chs else "general"
        self._hist:  dict[str, list]       = {c: [] for c in self._chs}
        self._last:  dict[str, str | None] = {c: None for c in self._chs}
        self._dm_peers: list[str]          = []

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def channels(self) -> list[str]:
        return list(self._chs)

    @property
    def active(self) -> str:
        return self._active

    @property
    def dm_peers(self) -> list[str]:
        return list(self._dm_peers)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def is_dm(self, key: str | None = None) -> bool:
        k = key if key is not None else self._active
        return k.startswith("dm:")

    def dm_key_for(self, peer: str) -> str:
        return f"dm:{peer}"

    # ── Navigation ────────────────────────────────────────────────────────────

    def switch(self, name: str):
        if name in self._hist:
            self._active = name

    def open_dm(self, peer: str) -> str:
        key = self.dm_key_for(peer)
        if peer not in self._dm_peers:
            self._dm_peers.append(peer)
            self._hist[key] = []
            self._last[key] = None
        self._active = key
        return key

    # ── Channel mutations ─────────────────────────────────────────────────────

    def set_channels(self, lst: list[str]):
        new_set = set(lst)
        for ch in lst:
            if ch not in self._hist:
                self._hist[ch] = []
                self._last[ch] = None
        for ch in list(self._chs):
            if ch not in new_set:
                del self._hist[ch]
                del self._last[ch]
                if self._active == ch:
                    self._active = lst[0] if lst else ""
        self._chs = list(lst)

    def can_add(self, name: str) -> bool:
        name = name.strip().lower().replace(" ", "-")
        return bool(name) and name not in self._chs and len(self._chs) < 20

    def can_rename(self, old: str, new: str) -> bool:
        new = new.strip().lower().replace(" ", "-")
        return bool(new) and new != old and old in self._chs

    def can_remove(self, name: str) -> bool:
        return name in self._chs and len(self._chs) > 1

    # ── History helpers ───────────────────────────────────────────────────────

    def push(self, ch: str, fn):
        """Append a history item to the channel or DM stream."""
        if ch in self._hist:
            self._hist[ch].append(fn)

    def history(self, ch: str) -> list:
        return list(self._hist.get(ch, []))

    def remove_message(self, ch: str, message_id: int) -> bool:
        items = self._hist.get(ch)
        if items is None:
            return False
        before = len(items)
        self._hist[ch] = [
            item for item in items
            if not (isinstance(item, dict) and item.get("id") == message_id)
        ]
        return len(self._hist[ch]) != before

    def remove_dm(self, peer: str) -> bool:
        key = self.dm_key_for(peer)
        if peer not in self._dm_peers or key not in self._hist:
            return False
        self._dm_peers.remove(peer)
        del self._hist[key]
        self._last.pop(key, None)
        if self._active == key:
            self._active = self._chs[0] if self._chs else "general"
        return True

    def is_compact(self, ch: str, username: str) -> bool:
        """Returns True when this message continues the previous sender's streak."""
        compact        = self._last.get(ch) == username
        self._last[ch] = username
        return compact

    def break_streak(self, ch: str):
        if ch in self._last:
            self._last[ch] = None
