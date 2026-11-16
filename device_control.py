"""Device control for PC + tablet.

Two layers (be aware of the difference):
  1. BROWSER actions - open websites, YouTube, Google, Maps, WhatsApp, calls... as tap-to-open links.
     Work on ANY device (PC, tablet, phone) and even when Jarvis runs in the cloud (Codespaces).
  2. PC control - open apps, volume, media keys, lock/sleep, type text, system info.
     Only possible on the machine Jarvis RUNS on. Run Jarvis on your PC with JARVIS_LOCAL=1 in .env,
     then open it from your tablet at  http://<pc-ip>:8501  - the tablet becomes the remote control.

Safety: no free-form shell. Apps come from an allow-list (plus apps YOU add), hotkeys are a fixed list,
typing/power actions need a confirmation tap, shutdown/restart need JARVIS_ALLOW_POWER=1.
"""
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import streamlit as st
import streamlit.components.v1 as components

from auth_utils import audit_log, has_permission
from data_paths import path as _dp
from html_safe import js

SYSTEM = platform.system()          # Windows / Darwin / Linux
APPS_FILE = _dp("pc_apps.json")


# ----------------------------- capability flags -----------------------------
def pc_enabled():
    return os.environ.get("JARVIS_LOCAL") == "1" and os.environ.get("JARVIS_PC_CONTROL", "1") == "1"


def power_enabled():
    return pc_enabled() and os.environ.get("JARVIS_ALLOW_POWER") == "1"


def _pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        return pyautogui
    except Exception:
        return None


def not_enabled_message():
    return ("🖥️ I can't touch a PC from here - Jarvis is running on a server (e.g. Codespaces). To let me control your PC: run Jarvis **on that PC** "
            "with `JARVIS_LOCAL=1` in `.env`, then open it from your tablet at `http://<pc-ip>:8501`. Web actions (YouTube, Google, Maps…) work anywhere.")


def lan_url(port=8501):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return f"http://{ip}:{port}"
    except Exception:
        return f"http://<pc-ip>:{port}"


# ----------------------------- apps -----------------------------
_BUILTIN = {
    "Windows": {"calculator": "calc", "notepad": "notepad", "paint": "mspaint", "chrome": "chrome", "edge": "msedge", "files": "explorer",
                "explorer": "explorer", "settings": "ms-settings:", "terminal": "wt", "command prompt": "cmd", "vs code": "code",
                "vscode": "code", "word": "winword", "excel": "excel", "powerpoint": "powerpnt", "spotify": "spotify",
                "task manager": "taskmgr", "camera": "microsoft.windows.camera:", "whatsapp": "whatsapp:"},
    "Darwin": {"calculator": "Calculator", "chrome": "Google Chrome", "safari": "Safari", "notes": "Notes", "terminal": "Terminal",
               "vs code": "Visual Studio Code", "vscode": "Visual Studio Code", "spotify": "Spotify", "settings": "System Settings",
               "files": "Finder", "finder": "Finder", "word": "Microsoft Word", "excel": "Microsoft Excel", "whatsapp": "WhatsApp"},
    "Linux": {"calculator": "gnome-calculator", "chrome": "google-chrome", "firefox": "firefox", "terminal": "x-terminal-emulator",
              "vs code": "code", "vscode": "code", "spotify": "spotify", "settings": "gnome-control-center", "files": "nautilus",
              "text editor": "gedit"},
}


def custom_apps():
    try:
        return json.load(open(APPS_FILE, encoding="utf-8"))
    except Exception:
        return {}


def save_custom_app(name, command):
    apps = custom_apps()
    apps[name.strip().lower()] = command.strip()
    json.dump(apps, open(APPS_FILE, "w", encoding="utf-8"), indent=2)


def remove_custom_app(name):
    apps = custom_apps()
    apps.pop(name, None)
    json.dump(apps, open(APPS_FILE, "w", encoding="utf-8"), indent=2)


def app_list():
    return {**_BUILTIN.get(SYSTEM, {}), **custom_apps()}


def open_app(name):
    apps = app_list()
    key = name.strip().lower()
    target = apps.get(key) or next((v for k, v in apps.items() if key in k or k in key), None)
    if not target:
        return False, f"I don't know an app called '{name}'. Add it in Device Control → My apps."
    try:
        if SYSTEM == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
        elif SYSTEM == "Darwin":
            subprocess.Popen(["open", "-a", target] if not target.startswith("/") else ["open", target])
        else:
            subprocess.Popen(shlex.split(target), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, f"Opened {name}."
    except Exception as e:
        return False, f"Could not open {name}: {e}"


# ----------------------------- PC actions -----------------------------
def _run(cmd):
    try:
        subprocess.run(cmd, check=True, timeout=10, capture_output=True)
        return True
    except Exception:
        return False


def volume(step=None, mute=False, level=None):
    pg = _pyautogui()
    if mute:
        if pg:
            pg.press("volumemute")
            return True, "Toggled mute."
        return False, "Install pyautogui (pip install pyautogui) for volume keys."
    if level is not None:
        level = max(0, min(100, int(level)))
        if SYSTEM == "Darwin" and _run(["osascript", "-e", f"set volume output volume {level}"]):
            return True, f"Volume set to {level}%."
        if SYSTEM == "Linux" and _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"]):
            return True, f"Volume set to {level}%."
        if pg and SYSTEM == "Windows":                       # Windows has no direct setter: go to 0, then up in 2% steps
            for _ in range(50):
                pg.press("volumedown")
            for _ in range(level // 2):
                pg.press("volumeup")
            return True, f"Volume set to about {level}%."
        return False, "Couldn't set the volume on this system."
    step = step or 10
    if SYSTEM == "Darwin" and _run(["osascript", "-e", f"set volume output volume ((output volume of (get volume settings)) + {step})"]):
        return True, f"Volume {'up' if step > 0 else 'down'}."
    if SYSTEM == "Linux" and _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{step:+d}%"]):
        return True, f"Volume {'up' if step > 0 else 'down'}."
    if pg:
        for _ in range(abs(step) // 2):
            pg.press("volumeup" if step > 0 else "volumedown")
        return True, f"Volume {'up' if step > 0 else 'down'}."
    return False, "Install pyautogui (pip install pyautogui) for volume control."


def media(action):
    pg = _pyautogui()
    if not pg:
        return False, "Install pyautogui (pip install pyautogui) for media keys."
    pg.press({"playpause": "playpause", "next": "nexttrack", "prev": "prevtrack"}[action])
    return True, {"playpause": "Play / pause sent.", "next": "Next track.", "prev": "Previous track."}[action]


def lock():
    cmds = {"Windows": ["rundll32.exe", "user32.dll,LockWorkStation"], "Darwin": ["pmset", "displaysleepnow"], "Linux": ["loginctl", "lock-session"]}
    return (True, "Locking the screen.") if _run(cmds[SYSTEM]) else (False, "Couldn't lock this system.")


def sleep_pc():
    cmds = {"Windows": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Darwin": ["pmset", "sleepnow"], "Linux": ["systemctl", "suspend"]}
    return (True, "Going to sleep.") if _run(cmds[SYSTEM]) else (False, "Couldn't sleep this system.")


def power(kind):
    if not power_enabled():
        return False, "Shutdown/restart are disabled. Set JARVIS_ALLOW_POWER=1 in .env to allow them."
    cmds = {("Windows", "shutdown"): ["shutdown", "/s", "/t", "30"], ("Windows", "restart"): ["shutdown", "/r", "/t", "30"],
            ("Darwin", "shutdown"): ["osascript", "-e", 'tell app "System Events" to shut down'],
            ("Darwin", "restart"): ["osascript", "-e", 'tell app "System Events" to restart'],
            ("Linux", "shutdown"): ["systemctl", "poweroff"], ("Linux", "restart"): ["systemctl", "reboot"]}
    ok = _run(cmds[(SYSTEM, kind)])
    return ok, (f"{kind.title()} started" + (" - on Windows run `shutdown /a` within 30 s to cancel." if SYSTEM == "Windows" else ".")) if ok else f"Couldn't {kind}."


def type_text(text):
    pg = _pyautogui()
    if not pg:
        return False, "Install pyautogui (pip install pyautogui) to type for you."
    pg.write(text, interval=0.02)
    return True, f"Typed {len(text)} characters."


HOTKEYS = {"copy": ("ctrl", "c"), "paste": ("ctrl", "v"), "undo": ("ctrl", "z"), "select all": ("ctrl", "a"), "new tab": ("ctrl", "t"),
           "close tab": ("ctrl", "w"), "refresh": ("f5",), "fullscreen": ("f11",), "show desktop": ("win", "d"), "switch window": ("alt", "tab"),
           "save": ("ctrl", "s"), "find": ("ctrl", "f")}


def hotkey(name):
    pg = _pyautogui()
    if not pg:
        return False, "Install pyautogui (pip install pyautogui) for hotkeys."
    keys = HOTKEYS[name]
    if SYSTEM == "Darwin":
        keys = tuple("command" if k == "ctrl" else k for k in keys)
    pg.hotkey(*keys)
    return True, f"Pressed {' + '.join(keys)}."


def system_info():
    lines = [f"{SYSTEM} · {platform.release()} · Python {platform.python_version()}"]
    try:
        import psutil
        lines.append(f"CPU {psutil.cpu_percent(interval=0.4)}% · RAM {psutil.virtual_memory().percent}% used")
        b = psutil.sensors_battery()
        if b:
            lines.append(f"Battery {int(b.percent)}%{' (charging)' if b.power_plugged else ''}")
    except Exception:
        lines.append("(install psutil for CPU / RAM / battery: pip install psutil)")
    return True, " · ".join(lines)


# ----------------------------- smart-device automations (webhooks / Home Assistant / Tasmota / IFTTT) -----------------------------
AUTOS_FILE = _dp("automations.json")
AUTO_PRESETS = {
    "Generic webhook (GET)": ("GET", "https://example.com/hook", "", ""),
    "Home Assistant - turn light ON": ("POST", "http://homeassistant.local:8123/api/services/light/turn_on", '{"entity_id": "light.living_room"}',
                                      '{"Authorization": "Bearer YOUR_LONG_LIVED_TOKEN"}'),
    "Home Assistant - turn light OFF": ("POST", "http://homeassistant.local:8123/api/services/light/turn_off", '{"entity_id": "light.living_room"}',
                                       '{"Authorization": "Bearer YOUR_LONG_LIVED_TOKEN"}'),
    "Tasmota / Sonoff plug ON": ("GET", "http://192.168.1.50/cm?cmnd=Power%20On", "", ""),
    "Tasmota / Sonoff plug OFF": ("GET", "http://192.168.1.50/cm?cmnd=Power%20Off", "", ""),
    "IFTTT webhook": ("GET", "https://maker.ifttt.com/trigger/EVENT_NAME/with/key/YOUR_KEY", "", ""),
}


def load_autos():
    try:
        return json.load(open(AUTOS_FILE, encoding="utf-8"))
    except Exception:
        return []


def _save_autos(items):
    json.dump(items, open(AUTOS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def add_auto(name, phrases, method, url, body="", headers="", confirm=False):
    items = [a for a in load_autos() if a["name"].lower() != name.strip().lower()]
    try:
        hdr = json.loads(headers) if headers.strip() else {}
    except Exception:
        hdr = {}
    items.append({"name": name.strip(), "phrases": [p.strip() for p in phrases.split(",") if p.strip()], "method": method, "url": url.strip(),
                  "body": body.strip(), "headers": hdr, "confirm": confirm})
    _save_autos(items)


def delete_auto(name):
    _save_autos([a for a in load_autos() if a["name"] != name])


def match_auto(low):
    for a in load_autos():
        for p in [a["name"].lower()] + [x.lower() for x in a.get("phrases", [])]:
            if p and re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", low):
                return a
    return None


def run_auto(name):
    a = next((x for x in load_autos() if x["name"] == name), None)
    if not a:
        return False, f"No automation called {name}."
    p = urllib.parse.urlparse(a["url"])
    if p.scheme not in ("http", "https") or not p.hostname or p.hostname.startswith("169.254."):
        return False, "That URL is not allowed (use http/https)."
    method = a.get("method", "GET")
    data = a["body"].encode() if method != "GET" and a.get("body") else None
    headers = dict(a.get("headers") or {})
    if data and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(a["url"], data=data, method=method, headers=headers), timeout=8) as r:
            return True, f"{a['name']} → done (HTTP {r.status})."
    except urllib.error.HTTPError as e:
        return False, f"{a['name']} failed: HTTP {e.code}."
    except Exception as e:
        return False, f"Couldn't reach the device ({str(e)[:70]}). If it is on your home Wi-Fi, Jarvis must run on that same network."


# ----------------------------- Android phone / tablet (ADB) -----------------------------
ADB_APPS = {"youtube": "com.google.android.youtube", "chrome": "com.android.chrome", "whatsapp": "com.whatsapp", "settings": "com.android.settings",
            "maps": "com.google.android.apps.maps", "gmail": "com.google.android.gm", "instagram": "com.instagram.android", "spotify": "com.spotify.music",
            "telegram": "org.telegram.messenger", "play store": "com.android.vending", "calculator": "com.google.android.calculator",
            "camera": "com.android.camera", "photos": "com.google.android.apps.photos", "classroom": "com.google.android.apps.classroom",
            "meet": "com.google.android.apps.tachyon", "drive": "com.google.android.apps.docs", "netflix": "com.netflix.mediaclient"}
ADB_KEYS = {"home": 3, "back": 4, "recents": 187, "power": 26, "volume_up": 24, "volume_down": 25, "mute": 164, "play_pause": 85,
            "next": 87, "prev": 88, "wake": 224, "enter": 66}


def adb_path():
    return shutil.which("adb") or os.environ.get("ADB_PATH") or None


def _adb(*args, timeout=15, binary=False):
    exe = adb_path()
    if not exe:
        return False, "adb is not installed"
    try:
        r = subprocess.run([exe, *args], capture_output=True, timeout=timeout)
        out = r.stdout if binary else r.stdout.decode("utf-8", "ignore").strip()
        return r.returncode == 0, out if r.returncode == 0 else (r.stderr.decode("utf-8", "ignore").strip() or out)
    except Exception as e:
        return False, str(e)


def adb_devices():
    ok, out = _adb("devices")
    return [l.split("\t")[0] for l in out.splitlines()[1:] if "\tdevice" in l] if ok else []


def adb_connect(addr):
    if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d{2,5})?", addr.strip()):
        return False, "Use the form 192.168.1.20:5555"
    ok, out = _adb("connect", addr.strip() if ":" in addr else addr.strip() + ":5555")
    return ok and "connected" in out.lower(), out


def _adb_ready():
    if not adb_path():
        return False, ("📱 ADB is not installed on the computer running Jarvis. Install Android platform-tools, turn on USB/Wireless debugging on the tablet, "
                       "then see Device Control → Android.")
    if not adb_devices():
        return False, "📱 No Android device connected. Plug it in (USB debugging ON) or connect over Wi-Fi in Device Control → Android."
    return True, ""


def _adb_shell(cmd):
    ok, msg = _adb_ready()
    if not ok:
        return False, msg
    return _adb("shell", cmd)


def adb_open_url(url):
    if not re.match(r"(https?|tel|sms|geo|mailto):", url):
        return False, "Unsupported link type."
    ok, out = _adb_shell(f"am start -a android.intent.action.VIEW -d {shlex.quote(url)}")
    return ok, "Opened on your device." if ok else out


def adb_open_app(name):
    key = name.strip().lower()
    pkg = ADB_APPS.get(key) or next((v for k, v in ADB_APPS.items() if k in key or key in k), None)
    if not pkg:
        return False, f"I don't know the Android app '{name}'. Known: " + ", ".join(sorted(ADB_APPS))
    ok, out = _adb_shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
    return ok, f"Opened {name} on your device." if ok else out


def adb_key(name, times=1):
    ok, msg = _adb_ready()
    if not ok:
        return False, msg
    for _ in range(max(1, times)):
        _adb("shell", "input", "keyevent", str(ADB_KEYS[name]))
    return True, f"Sent {name.replace('_', ' ')}."


def adb_brightness(level):
    level = max(0, min(100, int(level)))
    ok, out = _adb_shell(f"settings put system screen_brightness_mode 0; settings put system screen_brightness {int(level * 2.55)}")
    return ok, f"Brightness {level}%." if ok else out


def adb_radio(kind, on):
    return (lambda r: (r[0], f"{kind.title()} {'on' if on else 'off'}." if r[0] else r[1]))(_adb_shell(f"svc {kind} {'enable' if on else 'disable'}"))


def adb_screenshot():
    ok, msg = _adb_ready()
    if not ok:
        return False, msg
    ok, data = _adb("exec-out", "screencap", "-p", binary=True, timeout=20)
    if ok and data:
        st.session_state["device_image"] = data
        return True, "📸 Screenshot from your device:"
    return False, "Couldn't take a screenshot."


def adb_info():
    ok, msg = _adb_ready()
    if not ok:
        return False, msg
    _, model = _adb("shell", "getprop", "ro.product.model")
    _, ver = _adb("shell", "getprop", "ro.build.version.release")
    _, bat = _adb("shell", "dumpsys", "battery")
    lvl = re.search(r"level:\s*(\d+)", bat)
    return True, f"{model} · Android {ver}" + (f" · battery {lvl.group(1)}%" if lvl else "")


def adb_type(text):
    if not re.fullmatch(r"[\w .,@!?'\-]{1,120}", text):
        return False, "Only simple text can be typed (letters, numbers, spaces, . , @ ! ? ' -)."
    ok, out = _adb_shell(f"input text {shlex.quote(text.replace(' ', '%s'))}")
    return ok, f"Typed on your device." if ok else out


def adb_sms(number, text):
    num = re.sub(r"[^\d+]", "", number)
    ok, out = _adb_shell(f"am start -a android.intent.action.SENDTO -d sms:{num} --es sms_body {shlex.quote(text)}")
    return ok, "Message ready on your device - tap Send." if ok else out


_ADB_FUNCS = {"adb_open_url": adb_open_url, "adb_open_app": adb_open_app, "adb_key": adb_key, "adb_brightness": adb_brightness,
              "adb_radio": adb_radio, "adb_screenshot": adb_screenshot, "adb_info": adb_info, "adb_type": adb_type, "adb_sms": adb_sms}


def _adb_cmd(fn, args, label, risk="safe"):
    return {"type": "adb", "fn": fn, "args": args, "label": "📱 " + label, "risk": risk}


def parse_adb_command(low):
    """'open youtube on my tablet' / 'tablet volume up' / 'phone brightness 40' ..."""
    m = (re.match(r"(?:on|in|at|from)\s+(?:my\s+)?(?:tablet|phone|android|mobile)\b[,: ]*(.+)$", low)
         or re.match(r"(?:tablet|phone|android|mobile)\b[,: ]+(.+)$", low)
         or re.match(r"(.+?)\s+(?:on|in)\s+(?:my\s+)?(?:tablet|phone|android|mobile)$", low))
    if not m:
        return None
    x = m.group(1).strip()
    mm = re.match(r"(?:set )?brightness(?: to)? (\d{1,3})", x)
    if mm:
        return _adb_cmd("adb_brightness", [int(mm.group(1))], f"Brightness {mm.group(1)}%")
    mm = re.match(r"(?:turn )?(wifi|bluetooth) (on|off)$", x) or re.match(r"turn (on|off) (?:the )?(wifi|bluetooth)$", x)
    if mm:
        g = mm.groups()
        kind, on = (g[0], g[1]) if g[0] in ("wifi", "bluetooth") else (g[1], g[0])
        return _adb_cmd("adb_radio", [kind, on == "on"], f"{kind.title()} {on}")
    for pat, key, label, risk in [(r"(?:go )?home(?: screen)?$", "home", "Home", "safe"), (r"(?:go )?back$", "back", "Back", "safe"), (r"(?:recent apps|recents)$", "recents", "Recent apps", "safe"),
                                  (r"(?:wake up|wake|turn on (?:the )?screen)$", "wake", "Wake screen", "safe"), (r"(?:sleep|lock|turn off (?:the )?screen)$", "power", "Lock / sleep", "confirm"),
                                  (r"(?:volume up|louder|turn it up)$", "volume_up", "Volume up", "safe"), (r"(?:volume down|quieter|turn it down)$", "volume_down", "Volume down", "safe"),
                                  (r"mute$", "mute", "Mute", "safe"), (r"(?:pause|play|resume|play/pause)(?: music| video)?$", "play_pause", "Play / pause", "safe"),
                                  (r"next(?: song| track)?$", "next", "Next track", "safe"), (r"(?:previous|last)(?: song| track)$", "prev", "Previous track", "safe")]:
        if re.match(pat, x):
            return _adb_cmd("adb_key", [key] + ([3] if key.startswith("volume") else []), label, risk)
    if re.match(r"(?:take a )?screenshot$", x):
        return _adb_cmd("adb_screenshot", [], "Screenshot")
    if re.match(r"(?:battery|info|status|system info)$", x):
        return _adb_cmd("adb_info", [], "Device info")
    mm = re.match(r"(?:send (?:a )?(?:sms|text|message) to)\s+(\+?\d[\d\s-]{6,15}\d)\s*(?:saying|:)?\s*(.*)$", x)
    if mm:
        return _adb_cmd("adb_sms", [mm.group(1), mm.group(2)], f"SMS to {mm.group(1)}", "confirm")
    mm = re.match(r"type\s+(.+)$", x)
    if mm:
        return _adb_cmd("adb_type", [mm.group(1)], f"Type: {mm.group(1)[:30]}", "confirm")
    mm = re.match(r"(?:open|launch|start)\s+(?:the )?(.+)$", x)
    if mm and (mm.group(1) in ADB_APPS or any(k in mm.group(1) for k in ADB_APPS)):
        return _adb_cmd("adb_open_app", [mm.group(1)], f"Open {mm.group(1)}")
    inner = parse_device_command(x, _adb=False)
    if inner and inner["type"] == "web":
        return _adb_cmd("adb_open_url", [inner["url"]], inner["label"])
    return None


# ----------------------------- web (works everywhere) -----------------------------
SITES = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "gmail": "https://mail.google.com", "maps": "https://maps.google.com",
         "github": "https://github.com", "instagram": "https://www.instagram.com", "whatsapp": "https://web.whatsapp.com",
         "whatsapp web": "https://web.whatsapp.com", "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai", "drive": "https://drive.google.com",
         "google drive": "https://drive.google.com", "classroom": "https://classroom.google.com", "khan academy": "https://www.khanacademy.org",
         "ncert": "https://ncert.nic.in/textbook.php", "diksha": "https://diksha.gov.in", "cbse": "https://www.cbse.gov.in", "wikipedia": "https://www.wikipedia.org",
         "netflix": "https://www.netflix.com", "spotify": "https://open.spotify.com", "amazon": "https://www.amazon.in", "twitter": "https://x.com",
         "reddit": "https://www.reddit.com", "linkedin": "https://www.linkedin.com", "meet": "https://meet.google.com", "calendar": "https://calendar.google.com"}
_PAGES = {"study hub": "Study Hub", "syllabus": "Syllabus", "my syllabus": "Syllabus", "gallery": "Gallery", "time table": "Time Table", "timetable": "Time Table",
          "control panel": "Control Panel", "settings": "Control Panel", "chats": "My Data", "chats manager": "My Data",
          "danger zone": "My Data", "my data": "My Data", "data": "My Data", "action hub": "Action Hub", "device control": "Device Control",
          "admin": "Admin Dashboard", "admin dashboard": "Admin Dashboard", "realtime": "Realtime", "orb": "Realtime", "text chat": "Text Chat"}


def _q(t):
    return urllib.parse.quote_plus(t.strip())


_FILL = re.compile(r"^(?:(?:hey|ok|okay|hi|hello)[, ]+)?(?:jarvis[, ]+)?(?:(?:can|could|would|will) you\s+|i (?:want|need|would like) (?:you )?to\s+|i want it to\s+|"
                   r"i want to\s+|please\s+|just\s+|now\s+)*", re.I)


def _normalize(text):
    """'Hey Jarvis, can you please open YouTube for me?' -> 'open YouTube'."""
    t, prev = re.sub(r"[\u201c\u201d\"]", "", (text or "").strip()), None
    while prev != t:
        prev, t = t, _FILL.sub("", t).strip()
    t = t.rstrip("?.!, ")
    t = re.sub(r"[, ]+(for me|please|now|right now|quickly|again)$", "", t, flags=re.I)
    return t.strip().rstrip("?.!,").strip()


def parse_device_command(text, _adb=True):
    """Natural language -> {type: nav|web|pc, ...} or None. Deliberately strict so normal chat isn't hijacked."""
    t = _normalize(text)
    low = t.lower()
    if not low or low.startswith("/") or len(low.split()) > 16:
        return None
    if _adb:
        adb_cmd = parse_adb_command(low)
        if adb_cmd:
            return adb_cmd
    auto = match_auto(low)
    if auto:
        return {"type": "auto", "name": auto["name"], "label": f"Automation: {auto['name']}", "risk": "confirm" if auto.get("confirm") else "safe"}
    m = re.match(r"(?:please )?(?:go to|open|show me|take me to)\s+(?:the |my )?(.+)$", low)
    if m and m.group(1) in _PAGES:
        return {"type": "nav", "mode": _PAGES[m.group(1)], "label": m.group(1).title()}
    m = re.match(r"(?:please )?(?:play|search|find|watch)\s+(.+?)\s+(?:on|in)\s+youtube$", low) or re.match(r"youtube\s+(.+)$", low)
    if m:
        return {"type": "web", "label": f"YouTube: {m.group(1)}", "url": f"https://www.youtube.com/results?search_query={_q(m.group(1))}"}
    m = re.match(r"(?:please )?(?:google|search google for|search on google for)\s+(.+)$", low)
    if m:
        return {"type": "web", "label": f"Google: {m.group(1)}", "url": f"https://www.google.com/search?q={_q(m.group(1))}"}
    m = re.match(r"(?:please )?(?:navigate|directions?|route|take me|how do i get) to\s+(.+)$", low)
    if m:
        return {"type": "web", "label": f"Directions to {m.group(1)}", "url": f"https://www.google.com/maps/dir/?api=1&destination={_q(m.group(1))}"}
    m = re.match(r"(?:please )?(?:whatsapp|send whatsapp to|message)\s+(\+?\d[\d\s-]{7,15}\d)\s*(?:saying|:)?\s*(.*)$", low)
    if m:
        num = re.sub(r"\D", "", m.group(1))
        return {"type": "web", "label": f"WhatsApp {m.group(1)}", "url": f"https://wa.me/{num}?text={_q(m.group(2))}"}
    m = re.match(r"(?:please )?(?:call|dial|phone)\s+(\+?\d[\d\s-]{6,15}\d)$", low)
    if m:
        return {"type": "web", "label": f"Call {m.group(1)}", "url": "tel:" + re.sub(r"[^\d+]", "", m.group(1))}
    m = re.match(r"(?:please )?(?:open|launch|start|go to)\s+(?:the )?(.+)$", low)
    if m:
        target = m.group(1).strip()
        if target in SITES:
            return {"type": "web", "label": f"Open {target.title()}", "url": SITES[target]}
        if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+(/\S*)?", target):
            return {"type": "web", "label": f"Open {target}", "url": "https://" + target}
        apps = app_list()
        if len(target.split()) <= 3 and (target in apps or any(k == target or k in target.split() for k in apps)):
            return {"type": "pc", "fn": "open_app", "args": [target], "label": f"Open {target}", "risk": "safe"}
        if len(target.split()) <= 2 and re.fullmatch(r"[a-z0-9 ]{2,24}", target) and target not in _PAGES:
            guess = target.replace(" ", "")      # unknown name -> best-guess website + a Google fallback
            return {"type": "web", "label": f"Open {target}", "url": f"https://www.{guess}.com",
                    "alt": f"https://www.google.com/search?q={_q(target)}"}
        return None            # not an app/site we know -> treat as a normal chat message
    if re.fullmatch(r"(?:turn )?(?:the )?volume up|increase (?:the )?volume|louder|turn it up", low):
        return {"type": "pc", "fn": "volume", "args": [10], "label": "Volume up", "risk": "safe"}
    if re.fullmatch(r"(?:turn )?(?:the )?volume down|decrease (?:the )?volume|quieter|turn it down", low):
        return {"type": "pc", "fn": "volume", "args": [-10], "label": "Volume down", "risk": "safe"}
    if re.fullmatch(r"mute|unmute|toggle mute|mute (?:the )?(?:sound|volume)", low):
        return {"type": "pc", "fn": "volume", "args": [None, True], "label": "Mute / unmute", "risk": "safe"}
    m = re.match(r"set (?:the )?volume (?:to )?(\d{1,3})\s*%?$", low)
    if m:
        return {"type": "pc", "fn": "volume", "args": [None, False, int(m.group(1))], "label": f"Volume {m.group(1)}%", "risk": "safe"}
    if re.fullmatch(r"(?:pause|resume|play|stop)(?: the)?(?: music| song| video| media)?|play/pause", low) and low in ("pause", "resume", "pause music", "pause the music", "play music", "stop music", "pause the song", "pause video", "play/pause", "resume music"):
        return {"type": "pc", "fn": "media", "args": ["playpause"], "label": "Play / pause", "risk": "safe"}
    if re.fullmatch(r"next (?:song|track|video)|skip(?: this)?(?: song| track)?", low):
        return {"type": "pc", "fn": "media", "args": ["next"], "label": "Next track", "risk": "safe"}
    if re.fullmatch(r"(?:previous|last) (?:song|track)|go back a song", low):
        return {"type": "pc", "fn": "media", "args": ["prev"], "label": "Previous track", "risk": "safe"}
    m = re.match(r"play\s+(.+)$", low)
    if m and m.group(1) not in ("music", "song", "video", "media", "the music", "the song", "it", "this"):
        return {"type": "web", "label": f"YouTube: {m.group(1)}", "url": f"https://www.youtube.com/results?search_query={_q(m.group(1))}"}
    if re.fullmatch(r"lock (?:my |the )?(?:pc|computer|laptop|screen)", low):
        return {"type": "pc", "fn": "lock", "args": [], "label": "Lock the screen", "risk": "confirm"}
    if re.fullmatch(r"(?:put |send )?(?:my |the )?(?:pc|computer|laptop) (?:to )?sleep|sleep (?:my )?(?:pc|computer|laptop)", low):
        return {"type": "pc", "fn": "sleep_pc", "args": [], "label": "Put the PC to sleep", "risk": "confirm"}
    m = re.fullmatch(r"(shut ?down|restart|reboot)(?: my| the)? (?:pc|computer|laptop)", low)
    if m:
        k = "shutdown" if "shut" in m.group(1) else "restart"
        return {"type": "pc", "fn": "power", "args": [k], "label": f"{k.title()} the PC", "risk": "confirm"}
    m = re.match(r"type\s+(.+)$", t, flags=re.I)
    if m:
        return {"type": "pc", "fn": "type_text", "args": [m.group(1)], "label": f"Type: {m.group(1)[:40]}", "risk": "confirm"}
    if low in HOTKEYS:
        return {"type": "pc", "fn": "hotkey", "args": [low], "label": f"Hotkey: {low}", "risk": "safe"}
    if re.fullmatch(r"(?:battery|cpu|ram|system status|pc status|how(?:'s| is) my (?:pc|laptop|computer)|system info)", low):
        return {"type": "pc", "fn": "system_info", "args": [], "label": "System info", "risk": "safe"}
    return None


_FUNCS = {"open_app": open_app, "volume": volume, "media": media, "lock": lock, "sleep_pc": sleep_pc, "power": power,
          "type_text": type_text, "hotkey": hotkey, "system_info": system_info}


def execute(cmd, user=""):
    """Runs a parsed PC / Android / automation command. Returns (ok, message)."""
    if cmd["type"] == "auto":
        ok, msg = run_auto(cmd["name"])
        audit_log("device_action", user=user, detail=f"{cmd['label']} -> {'ok' if ok else 'fail'}")
        return ok, msg
    if cmd["type"] not in ("pc", "adb"):
        return False, "Not a device action."
    if not pc_enabled():
        return False, not_enabled_message()
    ok, msg = (_ADB_FUNCS if cmd["type"] == "adb" else _FUNCS)[cmd["fn"]](*cmd["args"])
    audit_log("device_action", user=user, detail=f"{cmd['label']} -> {'ok' if ok else 'fail'}")
    return ok, msg


def auto_open(url, label="link"):
    """Opens the link in a new tab. Uses the PARENT page (an iframe's own window.open is blocked by browsers); if the browser still
    blocks it, a big floating 'Tap to open' button appears on screen - one tap always works on PC and tablet."""
    components.html("""<script>(function(){const u=%s,l=%s,P=window.parent;let w=null;try{w=P.open(u,'_blank');}catch(e){}
    if(!w){const d=P.document;let b=d.getElementById('jv-open-banner');if(b)b.remove();b=d.createElement('a');b.id='jv-open-banner';b.href=u;b.target='_blank';
    b.rel='noopener';b.textContent='▶ Tap to open '+l;b.style.cssText='position:fixed;left:50%%;bottom:96px;transform:translateX(-50%%);z-index:99999;padding:14px 26px;'+
    'border-radius:999px;background:linear-gradient(90deg,#ff9a1f,#ff5a1a);color:#120800;font:600 16px sans-serif;text-decoration:none;box-shadow:0 8px 30px rgba(255,140,30,.6)';
    b.onclick=()=>setTimeout(()=>b.remove(),300);d.body.appendChild(b);setTimeout(()=>{try{b.remove()}catch(e){}},25000);}})();</script>""" % (js(url), js(label)), height=0)


# ----------------------------- page -----------------------------
def render_device_page(user, role):
    st.subheader("🖥️ Device Control")
    can_pc = has_permission(role, "device")
    on = pc_enabled()
    a, b, c = st.columns(3)
    a.metric("Jarvis runs on", f"{SYSTEM}")
    b.metric("PC control", "ON ✅" if on else "OFF")
    c.metric("Keys / pyautogui", "ready" if _pyautogui() else "not installed")
    if not on:
        st.info(not_enabled_message())
    st.markdown("#### 📱 Use your tablet as the remote")
    st.markdown("1. On your PC set `JARVIS_LOCAL=1` in `.env` and start: `streamlit run Jarvis.py --server.address 0.0.0.0`\n"
                "2. Open this address on your tablet (same Wi-Fi):")
    st.code(lan_url(), language=None)
    st.caption("Mic & voice need HTTPS on most tablets - on a home network use Chrome flag *Insecure origins treated as secure*, or a tunnel (Cloudflare / ngrok).")

    st.markdown("#### 🌐 Open anywhere (works on PC and tablet)")
    cols = st.columns(4)
    for i, (label, url) in enumerate([("▶️ YouTube", SITES["youtube"]), ("🔎 Google", SITES["google"]), ("📧 Gmail", SITES["gmail"]),
                                      ("🗺️ Maps", SITES["maps"]), ("💬 WhatsApp", SITES["whatsapp"]), ("📚 NCERT", SITES["ncert"]),
                                      ("🎓 Classroom", SITES["classroom"]), ("🧑‍💻 GitHub", SITES["github"])]):
        cols[i % 4].link_button(label, url, use_container_width=True)

    st.markdown("#### 🎛️ PC controls")
    if not (on and can_pc):
        st.caption("Available when PC control is ON and your role allows it (admin / power user).")
    else:
        r1 = st.columns(5)
        for col, (label, fn, args) in zip(r1, [("🔉 Vol −", volume, (-10,)), ("🔊 Vol +", volume, (10,)), ("🔇 Mute", volume, (None, True)),
                                                ("⏯️ Play/Pause", media, ("playpause",)), ("📊 System", system_info, ())]):
            if col.button(label, use_container_width=True, key=f"dv_{label}"):
                ok, msg = fn(*args)
                audit_log("device_action", user=user, detail=label)
                (st.success if ok else st.error)(msg)
        r2 = st.columns(5)
        for col, (label, fn, args) in zip(r2, [("⏮️ Prev", media, ("prev",)), ("⏭️ Next", media, ("next",)), ("🔒 Lock", lock, ()),
                                                ("😴 Sleep", sleep_pc, ()), ("📸 Screenshot", None, ())]):
            if col.button(label, use_container_width=True, key=f"dv2_{label}"):
                if fn is None:
                    from system_tools import take_screenshot
                    ok, res = take_screenshot()
                    st.image(res) if ok else st.error(res)
                else:
                    ok, msg = fn(*args)
                    audit_log("device_action", user=user, detail=label)
                    (st.success if ok else st.error)(msg)
        st.markdown("**Open an app**")
        apps = sorted(app_list())
        x, y = st.columns([4, 1])
        pick = x.selectbox("App", apps, label_visibility="collapsed", key="dv_app")
        if y.button("Open", use_container_width=True, key="dv_open"):
            ok, msg = open_app(pick)
            audit_log("device_action", user=user, detail=f"open {pick}")
            (st.success if ok else st.error)(msg)
        with st.expander("➕ My apps (add your own)"):
            st.caption("Only commands you add here (plus the built-ins) can ever be launched - Jarvis never runs free-form shell commands.")
            n, cmd = st.text_input("Name", key="dv_newname"), st.text_input("Command / app name / path", key="dv_newcmd")
            if st.button("Save app", disabled=not (n and cmd), key="dv_saveapp"):
                save_custom_app(n, cmd)
                st.success("Saved.")
                st.rerun()
            for k, v in custom_apps().items():
                p, q = st.columns([6, 1])
                p.markdown(f"**{k}** → `{v}`")
                if q.button("🗑", key=f"dv_rm_{k}"):
                    remove_custom_app(k)
                    st.rerun()
    st.markdown("#### 💡 Smart devices & automations")
    st.caption("Say *turn on the lights* (or clap twice) and Jarvis calls a web address you set - Home Assistant, a Tasmota/Sonoff plug, IFTTT, any webhook. "
               "The device must be reachable from where Jarvis runs (same Wi-Fi, or a cloud service like IFTTT).")
    if not can_pc:
        st.caption("Available to admin / power users.")
    else:
        for a in load_autos():
            x, y, z = st.columns([5, 1, 1])
            x.markdown(f"**{a['name']}** · say: {', '.join(a.get('phrases', [])[:3]) or a['name']}  \n`{a.get('method', 'GET')} {a['url'][:60]}`")
            if y.button("Test", key=f"au_t_{a['name']}"):
                ok, msg = run_auto(a["name"])
                (st.success if ok else st.error)(msg)
            if z.button("🗑", key=f"au_d_{a['name']}"):
                delete_auto(a["name"])
                st.rerun()
        with st.expander("➕ Add an automation"):
            preset = st.selectbox("Start from a template", list(AUTO_PRESETS), key="au_preset")
            pm, pu, pb, ph = AUTO_PRESETS[preset]
            name = st.text_input("Name", "lights on" if "ON" in preset or "plug ON" in preset else "my automation", key=f"au_n_{preset}")
            phrases = st.text_input("Phrases (comma-separated)", "turn on the lights, lights on", key=f"au_p_{preset}")
            method = st.selectbox("Method", ["GET", "POST"], index=0 if pm == "GET" else 1, key=f"au_m_{preset}")
            url = st.text_input("URL", pu, key=f"au_u_{preset}")
            body = st.text_area("Body (JSON, for POST)", pb, key=f"au_b_{preset}", height=70)
            headers = st.text_area("Headers (JSON, e.g. Authorization)", ph, key=f"au_h_{preset}", height=70)
            confirm = st.checkbox("Ask me to confirm before running", key=f"au_c_{preset}")
            if st.button("Save automation", disabled=not (name and url), key="au_save"):
                add_auto(name, phrases, method, url, body, headers, confirm)
                st.success("Saved.")
                st.rerun()

    st.markdown("#### 📱 Android tablet / phone (ADB)")
    st.caption("Jarvis runs on your PC and controls the tablet over USB or Wi-Fi: open apps, links, volume, media, brightness, Wi-Fi, screenshots, SMS drafts. "
               "Say **open YouTube on my tablet**, **tablet volume up**, **phone brightness 40**, **screenshot on my tablet**.")
    exe = adb_path()
    d1, d2 = st.columns(2)
    d1.metric("adb", "found ✅" if exe else "not installed")
    devs = adb_devices() if exe else []
    d2.metric("Connected devices", len(devs))
    if not exe:
        st.info("**Set up:** 1) Install *Android platform-tools* on the PC (adb in PATH)  2) Tablet: Settings → About → tap *Build number* 7 times → Developer options → "
                "turn on *USB debugging* (or *Wireless debugging*)  3) Plug in USB and tap *Allow*  4) Come back here.")
    elif can_pc and on:
        c1, c2 = st.columns([3, 1])
        addr = c1.text_input("Connect over Wi-Fi (IP:port)", placeholder="192.168.1.20:5555", key="adb_addr")
        if c2.button("Connect", key="adb_conn", disabled=not addr):
            ok, msg = adb_connect(addr)
            (st.success if ok else st.error)(msg)
        if devs:
            st.caption("Devices: " + ", ".join(devs))
            r = st.columns(5)
            for col, (label, fn, args) in zip(r, [("🏠 Home", adb_key, ("home",)), ("↩️ Back", adb_key, ("back",)), ("🔉 Vol −", adb_key, ("volume_down", 3)),
                                                  ("🔊 Vol +", adb_key, ("volume_up", 3)), ("⏯️ Play", adb_key, ("play_pause",))]):
                if col.button(label, use_container_width=True, key=f"ab_{label}"):
                    ok, msg = fn(*args)
                    (st.success if ok else st.error)(msg)
            r = st.columns(3)
            if r[0].button("📸 Screenshot", use_container_width=True, key="ab_shot"):
                ok, msg = adb_screenshot()
                st.image(st.session_state.pop("device_image")) if ok else st.error(msg)
            if r[1].button("ℹ️ Info", use_container_width=True, key="ab_info"):
                st.info(adb_info()[1])
            br = r[2].slider("Brightness", 0, 100, 60, key="ab_bri", label_visibility="collapsed")
            if st.button(f"Set brightness {br}%", key="ab_setbri"):
                st.info(adb_brightness(br)[1])
            x, y = st.columns([4, 1])
            app = x.selectbox("Open app on device", sorted(ADB_APPS), key="ab_app", label_visibility="collapsed")
            if y.button("Open", key="ab_open", use_container_width=True):
                ok, msg = adb_open_app(app)
                (st.success if ok else st.error)(msg)
    else:
        st.caption("Turn PC control ON (JARVIS_LOCAL=1) and use an admin / power-user account to control the device.")

    st.markdown("#### 🗣️ Try a command")
    st.caption("Say or type: *open calculator* · *play lo-fi on youtube* · *volume up* · *next song* · *directions to Cubbon Park* · *lock my pc* · *open study hub*")
    txt = st.text_input("Command", key="dv_cmd", placeholder="open youtube")
    if txt:
        cmd = parse_device_command(txt)
        if not cmd:
            st.warning("I didn't recognise that as a device command - it would be a normal chat message.")
        elif cmd["type"] == "web":
            st.link_button(f"▶ {cmd['label']}", cmd["url"])
        elif cmd["type"] == "nav":
            st.button(f"Go to {cmd['label']}", on_click=lambda m=cmd["mode"]: st.session_state.update(mode=m))
        elif not can_pc:
            st.error("Your role can't control the PC.")
        elif not on:
            st.info(not_enabled_message())
        else:
            if cmd["risk"] == "confirm" and not st.checkbox(f"Yes, really: {cmd['label']}", key="dv_confirm"):
                st.stop()
            if st.button("Run", key="dv_run"):
                ok, msg = execute(cmd, user)
                (st.success if ok else st.error)(msg)
