# Jarvis AI Core

## Quick start
1. `pip install -r requirements.txt`
2. Open the file **`.env`**, paste your keys (GROQ_API_KEY at least; ELEVENLABS_API_KEY for the realistic voice) and save.
   (You can also set keys later in the app: ☰ → Control Panel → 🔑 API Keys.)
3. `streamlit run Jarvis.py`

## Where is my data?  ->  `jarvis_data/`   (☰ → My Data shows everything)
- `users/<You>/` syllabus.json/.txt · exams.json/.txt · study_plan.json/.txt · notes · flashcards · quizzes · study_log · daily_routine
- `chat_logs/<You> chat with Jarvis.txt` every message, forever
- `gallery/` generated images · `syllabus_files/` your syllabus photos/PDFs
- `backups/` automatic daily zip (last 7) · plus manual backup / restore in My Data

## PC + tablet control
- Web actions (YouTube, Google, Maps, WhatsApp, call...) work on any device, even in Codespaces.
- Real PC control (open apps, volume, media keys, lock, type) only works on the machine Jarvis RUNS on:
  run `start_on_pc.bat` (Windows) or `./start_on_pc.sh`, then open `http://<pc-ip>:8501` on your tablet.
- Safety: allow-listed apps only, confirmation for lock/sleep/typing/power, shutdown needs JARVIS_ALLOW_POWER=1.

## More docs
- HOW_TO_CONTROL_DEVICES.md - PC, Android tablet (ADB), smart lights, double-clap, ElevenLabs setup
- Control Panel -> Diagnostics tells you which feature is not working and how to fix it

## Smarter AI
Agent mode (plans + uses web/calculator/your syllabus), learns from 👍/👎 and chats, tracks weak topics, daily brief. Set in Control Panel -> Behaviour.

## Chat commands
what to study next · make a time table · daily brief · open youtube · play <song> on youtube · volume up · next song ·
directions to <place> · open study hub · generate a 3D model of … · turn on the lights · open youtube on my tablet · /image … · /search … · remind me to … at 6 pm
