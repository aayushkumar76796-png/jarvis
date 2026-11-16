"""Background study alerts by EMAIL - runs even when the browser tab is closed
(as long as the Streamlit server / Codespace is awake).

Who gets mail: users who switched on "Email me study alerts" in the sidebar.
What is sent: today's timetable items (notify = Yes) and their due reminders.
Needs SMTP env vars - see email_utils.py. Without them mails are saved to outbox.json.
"""
import json
import os
import re
import threading
import time

import streamlit as st

from auth_utils import load_users
from email_utils import send_reply_email
from settings_utils import DEFAULTS, _load_all
import data_utils
import exam_utils
from time_utils import REMINDERS_FILE, _norm_time, load_timetable, now_ist

from data_paths import path as _dp

STATE_FILE = _dp("notify_state.json")
_lock = threading.Lock()
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def run_once():
    now = now_ist()
    state = _state()
    state = {k: v for k, v in state.items() if k.startswith(f"{now:%Y-%m-%d}")}   # keep today's keys only
    users = load_users()
    for user, saved in _load_all().items():
        s = {**DEFAULTS, **saved}
        to = s.get("alert_email") or users.get(user, {}).get("email", "")
        if not s.get("email_alerts") or not _EMAIL.match(to or ""):
            continue
        minutes_now = now.hour * 60 + now.minute
        for item in load_timetable():
            hhmm = _norm_time(item.get("time"))
            if item.get("notify") != "Yes" or not hhmm or item.get("email", True) is False:
                continue
            if 0 <= minutes_now - (int(hhmm[:2]) * 60 + int(hhmm[3:])) < 5:
                key = f"{now:%Y-%m-%d}|{user}|{item['time']}|{item['message']}"
                if key not in state:
                    state[key] = 1
                    send_reply_email(to, f"📚 Study time: {item['message']}",
                                     f"Hello {user},\n\nIt's {item['time']} - {item['message']}.\n\nYou've got this!\n- Jarvis")
        # ---- personal study plan (routine + chapters) and the daily exam digest ----
        try:
            for it in exam_utils.day_items(user):
                if it["kind"] in ("routine", "free", "revision") and not s.get("email_routine", True):
                    continue
                if 0 <= minutes_now - exam_utils._mins(it["t"]) < 5:
                    key = f"{now:%Y-%m-%d}|{user}|plan|{it['t']}|{it['text']}"
                    if key not in state:
                        state[key] = 1
                        label = re.sub(r"^[^A-Za-z(]+", "", it["text"])
                        extra = f"\n\nBest videos: {it['yt']}" if it.get("yt") else ""
                        send_reply_email(to, f"⏰ {exam_utils._hm(it['t'])} - {label[:70]}",
                                         f"Hello {user},\n\nNow: {label}{extra}\n\n- Jarvis")
            digest_key = f"{now:%Y-%m-%d}|{user}|digest"
            dt = s.get("exam_digest_time", "07:00")
            if digest_key not in state and minutes_now >= exam_utils._mins(dt):
                state[digest_key] = 1                      # one digest per day, even if there is nothing to say
                text = exam_utils.exam_digest_text(user)
                if text:
                    send_reply_email(to, f"📚 Exam digest - {now:%a %d %b}", text)
        except Exception:
            pass
        with _lock:
            try:
                data = json.load(open(REMINDERS_FILE, encoding="utf-8"))
            except Exception:
                data = {}
            changed = False
            for r in data.get(user, []):
                from datetime import datetime
                when = datetime.fromisoformat(r["when"])
                late = (now.replace(tzinfo=None) - when).total_seconds()
                if 0 <= late < 1800 and not r.get("emailed"):
                    r["emailed"] = True
                    changed = True
                    send_reply_email(to, f"⏰ Reminder: {r['text']}", f"Hello {user},\n\nReminder: {r['text']}\n\n- Jarvis")
            if changed:
                json.dump(data, open(REMINDERS_FILE, "w", encoding="utf-8"), indent=2)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"))


def _loop():
    while True:
        try:
            run_once()
        except Exception:
            pass
        try:
            data_utils.auto_backup()          # one zip per day in jarvis_data/backups/
        except Exception:
            pass
        time.sleep(30)


@st.cache_resource(show_spinner=False)
def start_notifier():
    """Starts the single background thread (cached, so only once per server process)."""
    t = threading.Thread(target=_loop, daemon=True, name="jarvis-notifier")
    t.start()
    return t
