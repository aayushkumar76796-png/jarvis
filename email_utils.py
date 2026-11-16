"""Email: real SMTP when configured, otherwise drafts are queued in outbox.json.

Set env vars to enable real sending (Gmail: use an App Password):
  JARVIS_SMTP_HOST=smtp.gmail.com  JARVIS_SMTP_PORT=587
  JARVIS_SMTP_USER=you@gmail.com   JARVIS_SMTP_PASS=app-password
"""
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from data_paths import path as _dp

LAST_STATUS = ""


def _queue(to_email, subject, body):
    path = _dp("outbox.json")
    try:
        box = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    except Exception:
        box = []
    box.append({"to": to_email, "subject": subject, "body": body, "queued": datetime.now().isoformat(timespec="seconds")})
    json.dump(box, open(path, "w", encoding="utf-8"), indent=2)


def send_reply_email(to_email, subject, body):
    """Returns True if sent or queued. Read email_utils.LAST_STATUS for the details."""
    global LAST_STATUS
    host, user, pw = (os.environ.get(k) for k in ("JARVIS_SMTP_HOST", "JARVIS_SMTP_USER", "JARVIS_SMTP_PASS"))
    if not (host and user and pw):
        _queue(to_email, subject, body)
        LAST_STATUS = "SMTP not configured - saved to jarvis_data/outbox.json instead of sending."
        return True
    try:
        msg = MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = user, to_email, subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(host, int(os.environ.get("JARVIS_SMTP_PORT", 587)), timeout=15) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        LAST_STATUS = "Email sent."
        return True
    except Exception as e:
        LAST_STATUS = f"Send failed: {e}"
        return False


def split_subject_body(draft):
    """Pulls 'Subject: ...' out of an AI-written draft."""
    lines = draft.strip().splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            return line.split(":", 1)[1].strip(), "\n".join(lines[i + 1:]).strip()
    return "", draft.strip()
