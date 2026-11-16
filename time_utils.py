"""Timetable, tasks and reminders - plus plain-English commands ("remind me to ... at 5 pm")."""
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta

import streamlit as st

from data_paths import path as _dp

TIMETABLE_FILE = _dp("timetable.json")
TASKS_FILE = _dp("tasks.json")
REMINDERS_FILE = _dp("reminders.json")
IST = timezone(timedelta(hours=5, minutes=30))


def _read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def now_ist():
    return datetime.now(IST)


# ---------------- timetable (global, original feature) ----------------
def load_timetable():
    data = _read(TIMETABLE_FILE, None)
    if data is not None:
        return data
    return [
        {"time": "08:00 AM", "notify": "Yes", "message": "Morning Mathematics Study Session"},
        {"time": "04:00 PM", "notify": "Yes", "message": "Physics Practice Worksheet"},
    ]


def save_timetable(schedule_data):
    _write(TIMETABLE_FILE, schedule_data)


def _norm_time(s):
    """'8:00 am' / '08:00 AM' / '20:00' -> 'HH:MM' (24h) or None."""
    s = (s or "").strip().upper().replace(".", "")
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None


def check_and_trigger_timetable():
    """Returns timetable messages due this minute (each fires once per day)."""
    now = now_ist()
    fired = st.session_state.setdefault("fired_alerts", set())
    out = []
    for item in load_timetable():
        hhmm = _norm_time(item.get("time"))
        if item.get("notify") == "Yes" and hhmm and 0 <= (now.hour * 60 + now.minute) - (int(hhmm[:2]) * 60 + int(hhmm[3:])) < 3:
            key = f"{now:%Y-%m-%d}-{item.get('time')}-{item.get('message')}"
            if key not in fired:
                fired.add(key)
                out.append(item.get("message"))
    return out


# ---------------- tasks (per user) ----------------
def list_tasks(user, include_done=False):
    tasks = _read(TASKS_FILE, {}).get(user, [])
    return tasks if include_done else [t for t in tasks if not t["done"]]


def add_task(user, text, due=""):
    data = _read(TASKS_FILE, {})
    data.setdefault(user, []).append({"id": uuid.uuid4().hex[:6], "text": text.strip(), "done": False,
                                      "due": due, "created": now_ist().isoformat(timespec="minutes")})
    _write(TASKS_FILE, data)


def set_task_done(user, task_id, done=True):
    data = _read(TASKS_FILE, {})
    for t in data.get(user, []):
        if t["id"] == task_id:
            t["done"] = done
    _write(TASKS_FILE, data)


def delete_task(user, task_id):
    data = _read(TASKS_FILE, {})
    data[user] = [t for t in data.get(user, []) if t["id"] != task_id]
    _write(TASKS_FILE, data)


# ---------------- reminders (per user, one-off) ----------------
def add_reminder(user, text, when):
    data = _read(REMINDERS_FILE, {})
    data.setdefault(user, []).append({"id": uuid.uuid4().hex[:6], "text": text, "when": when.isoformat(timespec="minutes"),
                                      "fired": False})
    _write(REMINDERS_FILE, data)


def list_reminders(user, only_pending=True):
    rs = _read(REMINDERS_FILE, {}).get(user, [])
    return [r for r in rs if not r["fired"]] if only_pending else rs


def delete_reminder(user, rid):
    data = _read(REMINDERS_FILE, {})
    data[user] = [r for r in data.get(user, []) if r["id"] != rid]
    _write(REMINDERS_FILE, data)


def check_due_reminders(user):
    data = _read(REMINDERS_FILE, {})
    due, now = [], now_ist().replace(tzinfo=None)
    for r in data.get(user, []):
        if not r["fired"] and datetime.fromisoformat(r["when"]) <= now:
            r["fired"] = True
            due.append(r["text"])
    if due:
        _write(REMINDERS_FILE, data)
    return due


def parse_when(text):
    """Finds 'in 10 minutes' / 'at 5 pm' / 'tomorrow at 7:30 am'. Returns (datetime|None, text_without_time)."""
    now = now_ist().replace(tzinfo=None, second=0, microsecond=0)
    m = re.search(r"\bin\s+(\d+)\s*(minute|min|hour|hr)s?\b", text, re.I)
    if m:
        n = int(m.group(1))
        delta = timedelta(hours=n) if m.group(2).lower() in ("hour", "hr") else timedelta(minutes=n)
        return now + delta, (text[:m.start()] + text[m.end():]).strip(" ,.")
    m = re.search(r"\b(today|tomorrow)?\s*at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.I)
    if m:
        hour, minute, ap = int(m.group(2)), int(m.group(3) or 0), (m.group(4) or "").lower()
        if ap == "pm" and hour < 12:
            hour += 12
        if ap == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None, text
        when = now.replace(hour=hour, minute=minute)
        if (m.group(1) or "").lower() == "tomorrow" or when <= now:
            when += timedelta(days=1)
        return when, (text[:m.start()] + text[m.end():]).strip(" ,.")
    return None, text


def get_schedule_summary(user):
    now = now_ist()
    lines = [f"**Now:** {now:%A, %d %b %Y - %I:%M %p} IST", "", "**Today's timetable**"]
    sched = sorted(load_timetable(), key=lambda i: _norm_time(i.get("time")) or "99")
    lines += [f"- {i['time']} - {i['message']}" for i in sched] or ["- (empty)"]
    rs = list_reminders(user)
    lines += ["", "**Reminders**"] + ([f"- {datetime.fromisoformat(r['when']):%d %b, %I:%M %p} - {r['text']}" for r in rs] or ["- none"])
    ts = list_tasks(user)
    lines += ["", "**Open tasks**"] + ([f"- {i}. {t['text']}" for i, t in enumerate(ts, 1)] or ["- none"])
    return "\n".join(lines)


def handle_conversational_command(user, text):
    """Returns a reply string if `text` was a task/reminder/schedule command, else None."""
    t = text.strip()
    low = t.lower()
    m = re.match(r"(?:please\s+)?remind me(?:\s+to)?\s+(.+)", t, re.I)
    if m:
        when, what = parse_when(m.group(1))
        if not when:
            return "I need a time, Sir - e.g. *remind me to revise physics at 6 pm* or *in 20 minutes*."
        add_reminder(user, what or "Reminder", when)
        return f"⏰ Reminder set for **{when:%a %d %b, %I:%M %p}**: {what or 'Reminder'}"
    m = re.match(r"(?:please\s+)?add (?:a )?(?:task|todo)(?: to my (?:tasks|todo list))?[:\s]+(.+)", t, re.I) \
        or re.match(r"(?:please\s+)?add (.+?) to my (?:tasks|todo(?: list)?|to-do list)", t, re.I)
    if m:
        add_task(user, m.group(1))
        return f"✅ Task added: **{m.group(1).strip()}**"
    m = re.match(r"(?:complete|finish|done with|mark done)(?: task)?\s+#?(\d+)", low)
    if m:
        ts = list_tasks(user)
        i = int(m.group(1)) - 1
        if 0 <= i < len(ts):
            set_task_done(user, ts[i]["id"])
            return f"🎉 Marked done: **{ts[i]['text']}**"
        return "I couldn't find that task number."
    if re.search(r"\b(my|show|list)\b.*\b(tasks|todo|to-do)\b", low) and len(low.split()) < 8:
        ts = list_tasks(user)
        return "**Open tasks**\n" + "\n".join(f"{i}. {t['text']}" for i, t in enumerate(ts, 1)) if ts else "No open tasks, Sir. 🎯"
    if re.search(r"(what'?s|show|check).*(schedule|timetable|agenda)|^check time", low):
        return get_schedule_summary(user)
    return None
