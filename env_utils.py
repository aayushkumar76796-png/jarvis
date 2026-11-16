"""Tiny .env loader (no extra package needed) + helpers to read/write keys safely.

Put your secrets in the file named  .env  next to Jarvis.py :
    GROQ_API_KEY=gsk_xxx
    ELEVENLABS_API_KEY=xxx
Real environment variables (Codespaces secrets etc.) always win over the .env file.
"""
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent

KNOWN_KEYS = [
    ("GROQ_API_KEY", "Groq - chat models + voice-to-text (console.groq.com)"),
    ("OPENAI_API_KEY", "OpenAI (optional endpoint)"),
    ("CUSTOM_LLM_API_KEY", "Any OpenAI-compatible endpoint (optional)"),
    ("ELEVENLABS_API_KEY", "ElevenLabs - realistic Jarvis voice (elevenlabs.io)"),
    ("ELEVENLABS_VOICE_ID", "ElevenLabs voice ID (the 'link' of your voice)"),
    ("JARVIS_SMTP_HOST", "Email: SMTP host, e.g. smtp.gmail.com"),
    ("JARVIS_SMTP_PORT", "Email: SMTP port, usually 587"),
    ("JARVIS_SMTP_USER", "Email: your address"),
    ("JARVIS_SMTP_PASS", "Email: app password"),
    ("JARVIS_ADMIN_EMAIL", "Where access requests are sent"),
]


def candidates():
    return [Path.cwd() / ".env", _HERE / ".env"]


def env_path():
    for p in candidates():
        if p.exists():
            return p
    return _HERE / ".env"


def _parse(text):
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        k, v = line.split("=", 1)
        v = v.strip()
        if v[:1] in "\"'" and v.count(v[0]) >= 2:
            v = v[1:v.index(v[0], 1)]
        elif " #" in v:
            v = v.split(" #", 1)[0].strip()
        out[k.strip()] = v
    return out


def load_env(override=False):
    """Loads .env into os.environ (existing variables are kept unless override=True). Returns the names loaded."""
    loaded = []
    for p in candidates():
        if p.exists():
            try:
                for k, v in _parse(p.read_text(encoding="utf-8")).items():
                    if v and (override or not os.environ.get(k)):
                        os.environ[k] = v
                        loaded.append(k)
            except Exception:
                pass
    return loaded


def set_key(name, value):
    """Saves/updates NAME=value in .env (keeps other lines) and applies it immediately."""
    p = env_path()
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    done = False
    for i, line in enumerate(lines):
        if line.strip().split("=", 1)[0].replace("export ", "").strip() == name:
            lines[i], done = f"{name}={value}", True
    if not done:
        lines.append(f"{name}={value}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    os.environ[name] = value


def mask(v):
    if not v:
        return "not set"
    return "••••" if len(v) <= 8 else f"{v[:3]}…{v[-4:]}"


load_env()
