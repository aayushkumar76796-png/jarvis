"""Run this once after downloading:   python setup_check.py
It tells you what is missing and what to do next. It changes nothing."""
import importlib.util
import os
import sys

OK, BAD = "✅", "❌"
print("\n=== JARVIS SETUP CHECK ===\n")
fail = 0

v = sys.version_info
print(f"{OK if v >= (3, 9) else BAD} Python {v.major}.{v.minor} (need 3.9 or newer)")
fail += v < (3, 9)

print("\nRequired packages (pip install -r requirements.txt):")
for mod, pkg in [("streamlit", "streamlit"), ("openai", "openai"), ("streamlit_mic_recorder", "streamlit-mic-recorder"), ("fpdf", "fpdf2"),
                 ("cryptography", "cryptography"), ("pypdf", "pypdf"), ("PIL", "pillow")]:
    ok = importlib.util.find_spec(mod) is not None
    fail += not ok
    print(f"  {OK if ok else BAD} {pkg}" + ("" if ok else f"   ->  pip install {pkg}"))

print("\nOptional - only if Jarvis runs on YOUR PC (pip install -r requirements-local.txt):")
for mod, pkg in [("pyautogui", "pyautogui"), ("psutil", "psutil"), ("pyperclip", "pyperclip"), ("pyttsx3", "pyttsx3")]:
    print(f"  {OK if importlib.util.find_spec(mod) else '➖'} {pkg}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_utils  # noqa: E402  (loads .env)

print(f"\n.env file: {env_utils.env_path()}  {OK if env_utils.env_path().exists() else BAD}")
for name, need, why in [("GROQ_API_KEY", True, "the AI brain + voice-to-text (free at console.groq.com)"),
                        ("ELEVENLABS_API_KEY", False, "realistic Jarvis voice (optional)"),
                        ("ELEVENLABS_VOICE_ID", False, "which ElevenLabs voice (optional)"),
                        ("JARVIS_SMTP_USER", False, "email alerts (optional)")]:
    has = bool(os.environ.get(name))
    fail += need and not has
    print(f"  {OK if has else (BAD if need else '➖')} {name:22} {'set' if has else 'EMPTY'}  - {why}")

print("\nPC control:", "ON" if os.environ.get("JARVIS_LOCAL") == "1" else "OFF (normal in Codespaces; set JARVIS_LOCAL=1 on your own PC)")
print("\n" + ("All good! Start Jarvis with:\n    streamlit run Jarvis.py\n" if not fail else
              f"{fail} thing(s) to fix above, then run this check again.\n"))
