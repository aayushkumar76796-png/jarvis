"""My Data: see where everything is saved, back it up / restore it, search it, export it as readable text."""
import glob
import io
import json
import os
import re
import zipfile
from datetime import date, datetime

import streamlit as st

import brain_utils
import study_utils as su
import time_utils
import transcript_utils as tlog
from crypto_utils import KEY_FILE
from data_paths import DATA_DIR, abs_dir, path as _dp
from settings_utils import load_user_settings

USER_DESC = {
    "syllabus.json": "My Syllabus", "syllabus.txt": "My Syllabus (readable copy)", "exams.json": "Exams + chapter progress",
    "exams.txt": "Exams (readable copy)", "study_plan.json": "Day-by-day study plan", "study_plan.txt": "Study plan (readable copy)",
    "daily_routine.json": "Daily routine + extra reminders", "notes.json": "Saved notes", "notes.txt": "Notes (readable copy)",
    "flashcards.json": "Flashcard decks + review schedule", "flashcards.txt": "Flashcards (readable copy)",
    "quizzes.json": "Quiz scores", "study_log.json": "Study minutes / streak log",
}
GLOBAL_DESC = {
    "users.json": "Accounts (passwords are hashed)", "user_settings.json": "Control Panel settings", "tasks.json": "Tasks (all users)",
    "reminders.json": "Reminders (all users)", "timetable.json": "Shared daily timetable", "memory_facts.json": "Facts Jarvis learned about you",
    "daily_brief.json": "Today's daily brief", "jarvis_chats.db": "Chat sessions (encrypted database)", "jarvis_memory.txt": "Jarvis master memory",
    "audit_log.jsonl": "Login / admin audit log", "outbox.json": "Emails saved when SMTP is off", "requests.json": "Access requests",
    "notify_state.json": "Email-alert bookkeeping", "feedback.json": "Your 👍/👎 ratings (Jarvis learns your style from them)",
}


def _size(n):
    return f"{n / 1024:.1f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


@st.cache_data(ttl=15, show_spinner=False)
def folder_stats():
    files = total = 0
    for root, _d, fs in os.walk(DATA_DIR):
        for f in fs:
            files += 1
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return files, total


# ----------------------------- inventory -----------------------------
def inventory(user):
    rows = []

    def add(p, what, scope):
        if os.path.isfile(p):
            s = os.stat(p)
            rows.append({"File": os.path.relpath(p, DATA_DIR), "What": what, "Whose": scope, "Size": _size(s.st_size),
                         "Modified": datetime.fromtimestamp(s.st_mtime).strftime("%d %b %H:%M"), "path": p})
    base = su.user_dir(user)
    for f, w in USER_DESC.items():
        add(os.path.join(base, f), w, "you")
    add(tlog.log_path(user), "Every chat message, forever (plain text)", "you")
    for f, w in GLOBAL_DESC.items():
        add(os.path.join(DATA_DIR, f), w, "shared")
    return rows


def _count_files(sub):
    d = os.path.join(DATA_DIR, sub)
    return sum(len(f) for _r, _d, f in os.walk(d)) if os.path.isdir(d) else 0


# ----------------------------- backup / restore -----------------------------
def backup_zip(include_key=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(DATA_DIR):
            if "backups" in os.path.relpath(root, DATA_DIR).split(os.sep):
                continue
            for f in files:
                if f.endswith(".tmp"):
                    continue
                full = os.path.join(root, f)
                z.write(full, os.path.join("jarvis_data", os.path.relpath(full, DATA_DIR)))
        if include_key and os.path.exists(KEY_FILE):
            z.write(KEY_FILE, "KEY/.jarvis_key")
        z.writestr("README.txt", f"Jarvis backup made {datetime.now():%d %b %Y %H:%M}.\n"
                                 "Restore it in Jarvis -> My Data -> Backup & Restore.\n"
                                 "KEY/.jarvis_key (if present) unlocks your encrypted chat history - keep this file private!\n")
    return buf.getvalue()


def restore_zip(data):
    """Safe restore (blocks '../' tricks). Returns (files_restored, messages)."""
    msgs, n, root = [], 0, os.path.abspath(DATA_DIR)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith("/") or name == "README.txt":
                continue
            if name == "KEY/.jarvis_key":
                if os.path.exists(KEY_FILE):
                    msgs.append("Kept your current encryption key (backup's key not applied).")
                else:
                    open(KEY_FILE, "wb").write(z.read(name))
                    msgs.append("Encryption key restored.")
                continue
            if not name.startswith("jarvis_data/"):
                continue
            dest = os.path.abspath(os.path.join(DATA_DIR, name[len("jarvis_data/"):]))
            if not dest.startswith(root + os.sep):
                msgs.append(f"Skipped unsafe path: {name}")
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(z.read(name))
            n += 1
    folder_stats.clear()
    return n, msgs


def list_backups():
    return sorted(glob.glob(os.path.join(DATA_DIR, "backups", "*.zip")), reverse=True)


def auto_backup(keep=7, force=False):
    """One zip per day in jarvis_data/backups/ (last `keep` kept). Called by the background thread."""
    p = _dp("backups", f"jarvis_backup_{date.today()}.zip")
    if os.path.exists(p) and not force:
        return None
    with open(p, "wb") as f:
        f.write(backup_zip(include_key=False))
    for old in list_backups()[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass
    return p


# ----------------------------- readable export + search -----------------------------
def _user_bundle(user):
    d = su.load(user)
    return {"study": d, "tasks": time_utils._read(time_utils.TASKS_FILE, {}).get(user, []),
            "reminders": time_utils._read(time_utils.REMINDERS_FILE, {}).get(user, []),
            "learned_facts": brain_utils.load_facts(user), "settings": load_user_settings(user)}


def export_all_txt(user):
    d, b = su.load(user), _user_bundle(user)
    parts = [f"JARVIS - EVERYTHING I SAVED FOR {user}", f"Exported {datetime.now():%d %b %Y %H:%M}", "=" * 60, "",
             su.txt_syllabus(user, d), "", su.txt_exams(user, d), "", su.txt_plan(user, d), "", su.txt_notes(user, d), "", su.txt_cards(user, d), "",
             "TASKS"] + [f"  [{'x' if t['done'] else ' '}] {t['text']}" for t in b["tasks"]] + ["", "REMINDERS"] + \
            [f"  {r['when']}  {r['text']}" for r in b["reminders"]] + ["", "WHAT JARVIS LEARNED ABOUT ME"] + [f"  - {f}" for f in b["learned_facts"]]
    return "\n".join(parts).encode("utf-8")


def export_all_json(user):
    return json.dumps(_user_bundle(user), indent=2, ensure_ascii=False).encode("utf-8")


def _snip(text, q, width=90):
    i = text.lower().find(q)
    return text[max(0, i - width): i + width].replace("\n", " ") if i >= 0 else text[:width]


def search_all(user, query):
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []
    d, out = su.load(user), []
    for sub, v in d["syllabus"].items():
        out += [{"Type": "Syllabus", "Where": sub, "Match": c} for c in v["chapters"] if q in c.lower()]
    for e in d["exams"]:
        if q in e.get("name", "").lower() or q in e.get("subject", "").lower():
            out.append({"Type": "Exam", "Where": e["name"], "Match": f"{e.get('subject')} - {e.get('date')}"})
        out += [{"Type": "Exam chapter", "Where": e["name"], "Match": c["name"]} for c in e.get("chapters", []) if q in c["name"].lower()]
    for n in d["notes"]:
        if q in (n["title"] + n["body"]).lower():
            out.append({"Type": "Note", "Where": n["title"], "Match": _snip(n["body"], q)})
    for deck, cards in d["decks"].items():
        out += [{"Type": "Flashcard", "Where": deck, "Match": c["q"]} for c in cards if q in (c["q"] + c["a"]).lower()]
    for t in time_utils._read(time_utils.TASKS_FILE, {}).get(user, []):
        if q in t["text"].lower():
            out.append({"Type": "Task", "Where": "done" if t["done"] else "open", "Match": t["text"]})
    for r in time_utils._read(time_utils.REMINDERS_FILE, {}).get(user, []):
        if q in r["text"].lower():
            out.append({"Type": "Reminder", "Where": r["when"], "Match": r["text"]})
    out += [{"Type": "Learned fact", "Where": "memory", "Match": f} for f in brain_utils.load_facts(user) if q in f.lower()]
    for e in reversed(tlog._entries(user)):
        if q in e.lower() and len(out) < 80:
            out.append({"Type": "Chat", "Where": e[1:20], "Match": _snip(e, q)})
    return out[:80]


# ----------------------------- page -----------------------------
def render_data_page(user):
    st.subheader("💾 My Data")
    st.caption("Everything you add to Jarvis - syllabus, exams, notes, plans, chats, images - is saved **automatically** as readable "
               "JSON and .txt files in ONE folder:")
    st.code(abs_dir(), language=None)
    files, total = folder_stats()
    backups = list_backups()
    a, b, c, d = st.columns(4)
    a.metric("Files", files)
    b.metric("Total size", _size(total))
    c.metric("Auto-backups", len(backups))
    d.metric("Last backup", os.path.basename(backups[0])[15:25] if backups else "none yet")
    st.info("☁️ **Codespaces:** this folder lives inside your Codespace. It stays when the Codespace sleeps, but is deleted if you delete the "
            "Codespace - so download a backup now and then (a new one is also saved here every day).")

    t_files, t_bak, t_search, t_exp, t_map = st.tabs(["📁 My files", "⬇️ Backup & Restore", "🔎 Search everything", "📄 Readable export", "🗺️ Folder map"])
    with t_files:
        rows = inventory(user)
        st.dataframe([{k: v for k, v in r.items() if k != "path"} for r in rows], hide_index=True, use_container_width=True)
        st.caption(f"📷 {_count_files('gallery')} gallery file(s) · 🖼️ {_count_files('syllabus_files')} syllabus photo(s)/PDF(s) · 💬 chat log lines are in chat_logs/")
        if rows:
            pick = st.selectbox("Open a file", [r["File"] for r in rows], key="data_pick")
            row = next(r for r in rows if r["File"] == pick)
            raw = open(row["path"], "rb").read()
            st.download_button("⬇️ Download this file", raw, os.path.basename(row["path"]), use_container_width=True)
            if row["path"].endswith((".json", ".txt", ".jsonl")) and len(raw) < 400_000:
                st.code(raw.decode("utf-8", "ignore")[:6000], language="json" if row["path"].endswith("json") else None)
    with t_bak:
        k = st.checkbox("Include my encryption key in the backup", value=True,
                        help="Needed to read your encrypted chat list after restoring on another machine. Keep the zip private.")
        x, y = st.columns(2)
        if x.button("📦 Prepare full backup (.zip)", use_container_width=True, type="primary"):
            st.session_state.backup_bytes = backup_zip(k)
        if y.button("💾 Save a backup on the server now", use_container_width=True):
            auto_backup(force=True)
            folder_stats.clear()
            st.success("Saved to jarvis_data/backups/")
        if st.session_state.get("backup_bytes"):
            st.download_button("⬇️ Download backup", st.session_state.backup_bytes, f"jarvis_backup_{date.today()}.zip", "application/zip",
                               use_container_width=True)
        if backups:
            pick = st.selectbox("Server backups", backups, format_func=os.path.basename, key="bak_pick")
            st.download_button("⬇️ Download that backup", open(pick, "rb").read(), os.path.basename(pick), "application/zip")
        st.markdown("**Restore**")
        up = st.file_uploader("Upload a Jarvis backup (.zip)", type=["zip"], key="restore_zip")
        if up and st.checkbox("Yes - overwrite matching files with this backup", key="restore_ok") and st.button("♻️ Restore now"):
            try:
                n, msgs = restore_zip(up.getvalue())
                st.success(f"Restored {n} file(s). Refresh the page to load them.")
                for m in msgs:
                    st.caption(m)
            except Exception as e:
                st.error(f"Restore failed: {e}")
    with t_search:
        q = st.text_input("Search your syllabus, exams, notes, flashcards, tasks, reminders, facts and chats", placeholder="e.g. trigonometry",
                          key="data_search")
        if q:
            res = search_all(user, q)
            st.caption(f"{len(res)} result(s)")
            st.dataframe(res, hide_index=True, use_container_width=True)
    with t_exp:
        st.caption("One readable text file with everything (chat log excluded - download it from Chats Manager).")
        e1, e2 = st.columns(2)
        e1.download_button("⬇️ Everything as .txt", export_all_txt(user), f"{user}_everything.txt", "text/plain", use_container_width=True)
        e2.download_button("⬇️ Everything as .json", export_all_json(user), f"{user}_everything.json", "application/json", use_container_width=True)
    with t_map:
        from data_paths import __doc__ as tree
        st.code(tree, language=None)
