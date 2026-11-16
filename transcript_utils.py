"""Permanent, human-readable chat log:  chat_logs/<User> chat with Jarvis.txt

* Every message (yours and Jarvis's) is appended here forever.
* "Clear chat" only clears the SCREEN - this file is never touched.
* Jarvis reads this file to remember past conversations (recent tail + keyword recall).
"""
import os
import re
from datetime import datetime

from data_paths import path as _dp

LOG_DIR = _dp("chat_logs")
_ENTRY_SPLIT = re.compile(r"\n(?=\[\d{4}-\d{2}-\d{2} )")


def _safe(name):
    return "".join(c for c in name if c.isalnum() or c in " _-").strip() or "user"


def log_path(username):
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, f"{_safe(username)} chat with Jarvis.txt")


def append_turn(username, role, text):
    who = username if role == "user" else "Jarvis"
    body = (text or "").strip().replace("\r", "")
    try:
        with open(log_path(username), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {who}: {body}\n\n")
    except Exception:
        pass


def _entries(username):
    path = log_path(username)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [e.strip() for e in _ENTRY_SPLIT.split(f.read()) if e.strip()]
    except Exception:
        return []


def read_recent(username, max_chars=2500):
    """Tail of the log - what you were talking about most recently."""
    out, size = [], 0
    for e in reversed(_entries(username)):
        size += len(e)
        if size > max_chars:
            break
        out.append(e[:700])
    return "\n".join(reversed(out))


def recall(username, query, limit=4, skip_recent=6):
    """Keyword search of the whole log, ignoring the newest few entries (they are already in context)."""
    words = {w for w in re.findall(r"[a-zA-Z0-9]{4,}", (query or "").lower())}
    entries = _entries(username)
    if not words or len(entries) <= skip_recent:
        return []
    scored = []
    for i, e in enumerate(entries[:-skip_recent]):
        score = sum(1 for w in words if w in e.lower())
        if score >= 2 or (score == 1 and any(len(w) >= 8 and w in e.lower() for w in words)):
            scored.append((score, i, e[:500]))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [e for _, _, e in scored[:limit]]


def delete_log(username):
    """Danger Zone only - permanently deletes the chat .txt."""
    try:
        os.remove(log_path(username))
        return True
    except OSError:
        return False


def stats(username):
    path = log_path(username)
    return {"entries": len(_entries(username)), "bytes": os.path.getsize(path) if os.path.exists(path) else 0}


def read_all_bytes(username):
    path = log_path(username)
    return open(path, "rb").read() if os.path.exists(path) else b""


def import_legacy(username):
    """If an old chat_history_<user>.txt exists and no new log yet, carry it over once."""
    safe = "".join(c for c in username if c.isalnum() or c in "_-")
    old = f"chat_history_{safe}.txt"
    if os.path.exists(old) and not os.path.exists(log_path(username)):
        try:
            for block in open(old, encoding="utf-8").read().split("---MESSAGE_SPLIT---"):
                if ":" in block:
                    role, content = block.strip().split(":", 1)
                    if role.strip().lower() in ("user", "assistant") and content.strip():
                        append_turn(username, role.strip().lower(), content)
        except Exception:
            pass
