# START HERE - Jarvis setup in 10 minutes

## 1. What you must change
**Only ONE file: `.env`** (open it in any text editor). Paste your keys after the `=` sign, save, done.
Do NOT edit any `.py` file.

| In `.env` | Needed? | Where to get it |
|---|---|---|
| `GROQ_API_KEY=` | **YES** | console.groq.com → API Keys → Create (free) |
| `ELEVENLABS_API_KEY=` | optional (realistic voice) | elevenlabs.io → Profile → API Keys (allow Text-to-Speech) |
| `ELEVENLABS_VOICE_ID=` | optional | elevenlabs.io → Voices → copy a voice's ID |
| `JARVIS_SMTP_USER=` / `JARVIS_SMTP_PASS=` | optional (email alerts) | Gmail → Google Account → Security → 2-Step Verification → **App passwords** |
| `JARVIS_ADMIN_EMAIL=` | optional | your email |
| `JARVIS_LOCAL=1` | only on your own PC (PC control) | - |

You can also add/change keys later inside the app: ☰ → Control Panel → 🔑 API Keys (admin only).

## 2. All the pip packages
```
pip install -r requirements.txt
```
installs: `streamlit  openai  streamlit-mic-recorder  fpdf2  cryptography  pypdf  pillow`

Only if Jarvis runs on **your own PC** (to control it):
```
pip install -r requirements-local.txt
```
installs: `pyautogui  psutil  pyperclip  pyttsx3`

Python 3.9 or newer is needed.

## 3A. Start in GitHub Codespaces (what you use now)
1. Upload `jarvis.zip` to your Codespace (drag it into the file list) and unzip: `unzip jarvis.zip`
2. `cd jarvis`
3. `pip install -r requirements.txt`
4. Open `.env`, paste `GROQ_API_KEY=...` (and the others), save
5. `python setup_check.py`  ← tells you if anything is missing
6. `streamlit run Jarvis.py`
7. Bottom panel → **Ports** → port **8501** → click the 🌐 globe icon (set Visibility to *Private*)
8. Log in: user **Aayush**, passcode **123098** → then ☰ → Control Panel → Account → **change the passcode**

## 3B. Start on your own PC (needed to control the PC / tablet / lights)
1. Install Python 3.9+ (tick "Add to PATH"), unzip `jarvis.zip`
2. Edit `.env` (keys as above)
3. Windows: double-click `start_on_pc.bat`    Mac/Linux: `./start_on_pc.sh`
4. Open `http://localhost:8501` on the PC, or `http://<pc-ip>:8501` on your tablet (Device Control page shows the address)

## 4. First 10 minutes inside Jarvis
1. ☰ → **My Syllabus** → add subjects + chapters (type, photo, or PDF)
2. ☰ → **Study Hub → Exams & Planner → Add Exam** (pick subjects + chapters, date, time)
3. **Routine & Daily Schedule** → set wake / school / dinner / sleep + extra reminders
4. In chat type **make a time table**, then **what to study next**
5. ☰ → Control Panel → **Alerts** → switch on email alerts, add your address, press *Send test email*
6. ☰ → Control Panel → **Voice** → press *Test ElevenLabs now* ; **Diagnostics** shows what isn't working

## 5. Where your data is
Everything is saved in the folder **`jarvis_data/`** (readable .json and .txt files). ☰ → **My Data** shows, backs up and restores it.
When you install a newer Jarvis, keep these three: `jarvis_data/`, `.env`, `.jarvis_key`.

## 6. If something doesn't work
| Problem | Fix |
|---|---|
| "GROQ_API_KEY missing" / no answers | paste the key in `.env`, then Control Panel → API Keys → **Reload .env** (or restart) |
| ElevenLabs silent | Control Panel → Voice → **Test ElevenLabs now** (shows the exact reason); free plans: use a *premade* voice |
| Link doesn't open | press the **Tap to open** button that appears; allow pop-ups for the site |
| Mic / clap / wake word don't work | allow Microphone for the site in the browser; tablets need HTTPS |
| No emails | fill the `JARVIS_SMTP_*` lines; Gmail needs an *App password*; Codespaces sleeps when idle |
| "No module named …" | `pip install -r requirements.txt` again, then `python setup_check.py` |
| Controlling PC says "I can't touch a PC" | you are in the cloud - run on your PC with `JARVIS_LOCAL=1` |
| Anything else | ☰ → Control Panel → **🩺 Diagnostics** |

More: `HOW_TO_CONTROL_DEVICES.md` (PC, Android tablet, lights, clap, ElevenLabs details).
