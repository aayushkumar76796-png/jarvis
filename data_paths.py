"""ONE folder for everything Jarvis saves:  jarvis_data/

    jarvis_data/
      users.json                      accounts (passwords hashed)
      user_settings.json              each user's Control Panel settings
      users/<User>/                   per-user study data - human-readable JSON + .txt copies
          syllabus.json  syllabus.txt     exams.json  exams.txt      study_plan.json  study_plan.txt
          flashcards.json flashcards.txt  notes.json  notes.txt      quizzes.json     study_log.json
          daily_routine.json
      chat_logs/<User> chat with Jarvis.txt   every message, forever (plain text)
      gallery/<User>/                 generated images + index.json
      syllabus_files/                 your syllabus photos / PDFs
      jarvis_chats.db                 chat sessions (encrypted)
      tasks.json reminders.json timetable.json memory_facts.json daily_brief.json ...
      backups/                        automatic daily backups (zip)

Override the location with the env var JARVIS_DATA_DIR. Files from older versions (saved in the project
folder) are moved here automatically the first time Jarvis starts.
"""
import os
import shutil

import env_utils   # loads .env first, so JARVIS_DATA_DIR etc. are honoured

DATA_DIR = os.environ.get("JARVIS_DATA_DIR", "jarvis_data")

_LEGACY_FILES = ["users.json", "jarvis_memory.txt", "audit_log.jsonl", "user_settings.json", "timetable.json", "tasks.json",
                 "reminders.json", "notify_state.json", "memory_facts.json", "daily_brief.json", "jarvis_chats.db",
                 "outbox.json", "requests.json", "study_data.json"]
_LEGACY_DIRS = {"chat_logs": "chat_logs", "jarvis_gallery": "gallery", "syllabus_files": "syllabus_files"}


def path(*parts):
    """Absolute-ish path inside the data folder (parent folders are created)."""
    p = os.path.join(DATA_DIR, *parts)
    os.makedirs(os.path.dirname(p) if os.path.splitext(p)[1] else p, exist_ok=True)
    return p


def abs_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.abspath(DATA_DIR)


def migrate_legacy():
    """Moves files saved by older versions (project root) into jarvis_data/. Never overwrites existing files."""
    os.makedirs(DATA_DIR, exist_ok=True)
    moved = []
    try:
        for f in _LEGACY_FILES:
            if os.path.exists(f) and not os.path.exists(os.path.join(DATA_DIR, f)):
                shutil.move(f, os.path.join(DATA_DIR, f))
                moved.append(f)
        for old, new in _LEGACY_DIRS.items():
            if os.path.isdir(old) and not os.path.exists(os.path.join(DATA_DIR, new)):
                shutil.move(old, os.path.join(DATA_DIR, new))
                moved.append(old + "/")
    except Exception:
        pass
    return moved


MIGRATED = migrate_legacy()
