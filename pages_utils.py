"""Full-page tools that used to crowd the sidebar: Chats Manager, Danger Zone, Control Panel."""
import os
from datetime import date, datetime

import streamlit as st

import email_utils
import brain_utils
import gallery_utils
import study_utils
import transcript_utils as tlog
from auth_utils import audit_log, change_password, has_permission, load_users, uses_default_password
from crypto_utils import encryption_active, verify_password
from email_utils import send_reply_email
from history_utils import (delete_all_sessions, export_all_json, export_all_markdown, export_json, export_markdown, export_txt,
                           list_sessions, search_sessions)
from image_generation_and_pdf import STYLES
from settings_utils import DEFAULTS, ENDPOINTS, TTS_ENGINES, VOICE_PREFS, get_settings, save_user_settings
from sidebar_utils import clear_chat, delete_session_cb, load_session, new_chat, pin_cb, rename_cb
import env_utils
from speech_utils import effective_engine, eleven_ready, eleven_test, eleven_voices, speak_and_notify
from theme_utils import PALETTES
import time_utils


# =============================== CHATS MANAGER ===============================
def _group_of(iso):
    delta = (date.today() - datetime.fromisoformat(iso).date()).days
    return "Today" if delta <= 0 else "Yesterday" if delta == 1 else "Previous 7 days" if delta <= 7 else "Older"


def render_chats_manager():
    user, role = st.session_state.current_user, st.session_state.get("role", "normal user")
    current = st.session_state.get("session_id")
    st.subheader("🗂️ Chats Manager")
    a, b = st.columns(2)
    a.button("＋ New chat", on_click=new_chat, type="primary", use_container_width=True, key="cm_new")
    b.button("🧹 Clear screen", on_click=clear_chat, use_container_width=True, key="cm_clear",
             help="Clears what you see. Everything stays saved.")
    ls = tlog.stats(user)
    st.caption(f"📝 `{os.path.basename(tlog.log_path(user))}` · {ls['entries']} entries · permanent log (never deleted by Clear)")

    q = st.text_input("Search chats", placeholder="🔍 Search titles and messages…", label_visibility="collapsed", key="cm_search")
    sessions = list_sessions(user, 500)
    if q:
        ids = set(search_sessions(user, q))
        sessions = [x for x in sessions if q.lower() in x["title"].lower() or x["id"] in ids]
    st.caption(f"{len(sessions)} chat(s)")
    buckets = {"📌 Pinned": [x for x in sessions if x["pinned"]]}
    for x in sessions:
        if not x["pinned"]:
            buckets.setdefault(_group_of(x["updated"]), []).append(x)
    for label in ("📌 Pinned", "Today", "Yesterday", "Previous 7 days", "Older"):
        items = buckets.get(label, [])
        if not items:
            continue
        st.markdown(f'<div class="jv-grp">{label}</div>', unsafe_allow_html=True)
        for sess in items:
            c1, c2, c3 = st.columns([7, 2, 1])
            c1.button(("● " if sess["id"] == current else "") + sess["title"], key=f"cm_load_{sess['id']}", on_click=load_session,
                      args=(sess["id"],), use_container_width=True, help=sess["updated"].replace("T", " "))
            with c2.popover("Edit", use_container_width=True):
                st.text_input("Rename", sess["title"], key=f"rn_{sess['id']}")
                st.button("💾 Save name", key=f"rnb_{sess['id']}", on_click=rename_cb, args=(sess["id"],), use_container_width=True)
                st.button("📌 Unpin" if sess["pinned"] else "📌 Pin to top", key=f"pin_{sess['id']}", on_click=pin_cb,
                          args=(sess["id"], not sess["pinned"]), use_container_width=True)
            c3.button("🗑", key=f"cm_del_{sess['id']}", on_click=delete_session_cb, args=(sess["id"],), help="Delete this chat")

    st.markdown("### ⬇️ Download")
    if has_permission(role, "export"):
        d1, d2, d3 = st.columns(3)
        d1.download_button("All chats (JSON)", export_all_json(user), f"{user}_all_chats.json", "application/json", use_container_width=True)
        d2.download_button("All chats (Markdown)", export_all_markdown(user), f"{user}_all_chats.md", "text/markdown", use_container_width=True)
        d3.download_button("Full chat .txt log", tlog.read_all_bytes(user), os.path.basename(tlog.log_path(user)), "text/plain",
                           use_container_width=True, disabled=not ls["entries"])
        msgs = st.session_state.get("messages", [])
        if msgs:
            st.caption("Current chat only:")
            e1, e2, e3 = st.columns(3)
            e1.download_button("JSON", export_json(msgs), "chat.json", "application/json", use_container_width=True)
            e2.download_button("Markdown", export_markdown(msgs), "chat.md", "text/markdown", use_container_width=True)
            e3.download_button("Text", export_txt(msgs), "chat.txt", "text/plain", use_container_width=True)
    else:
        st.info("Your role cannot export chats.")

    st.markdown("### 🗑️ Delete")
    st.caption("Removes the chat list only. The permanent `.txt` log stays (delete it from the Danger Zone if you really want to).")
    if st.checkbox("I want to delete ALL my chats", key="cm_confirm"):
        st.button("Delete all chats", on_click=lambda: (delete_all_sessions(user), new_chat()), type="primary", key="cm_wipe")


# =============================== DANGER ZONE ===============================
def render_danger_zone():
    user = st.session_state.current_user
    st.subheader("🧨 Danger Zone")
    st.warning("Everything here is permanent. Each action needs its own confirmation.")

    c1, c2 = st.columns(2)
    c1.markdown("🔒 **Encryption:** " + ("active - chat list is encrypted at rest" if encryption_active()
                                         else "⚠️ OFF - run `pip install cryptography` and restart"))
    c2.markdown("🔑 **Passcode:** " + ("⚠️ default passcode in use - change it in Control Panel → Account"
                                     if uses_default_password(user) else "custom ✔️"))

    with st.expander("🗂️ Delete saved chat list"):
        st.caption("Removes sidebar/Chats Manager chats. The `.txt` log and gallery stay.")
        if st.checkbox("Yes, delete my chat list", key="dz_chats"):
            st.button("Delete chat list", on_click=lambda: (delete_all_sessions(user), new_chat()), key="dz_chats_go")
    with st.expander("📝 Delete the permanent chat .txt log"):
        n = tlog.stats(user)["entries"]
        st.caption(f"`{os.path.basename(tlog.log_path(user))}` holds {n} entries - Jarvis's long-term memory of you.")
        if st.text_input("Type DELETE to confirm", key="dz_txt_confirm") == "DELETE" and st.button("Permanently delete the .txt log", key="dz_txt_go"):
            audit_log("txt_log_deleted", user=user)
            st.success("Deleted." if tlog.delete_log(user) else "Nothing to delete.")
    with st.expander("🖼️ Delete all generated images"):
        st.caption(f"{len(gallery_utils.list_images(user))} image(s) in your gallery.")
        if st.checkbox("Yes, delete every image", key="dz_gal") and st.button("Delete gallery", key="dz_gal_go"):
            gallery_utils.delete_all(user)
            st.success("Gallery emptied.")
    with st.expander("📚 Reset study data"):
        parts = st.multiselect("What to wipe", ["decks", "notes", "quizzes", "logs", "exams", "plan", "routine", "syllabus"], key="dz_study_sel")
        if parts and st.checkbox("Yes, wipe the selected study data", key="dz_study") and st.button("Wipe study data", key="dz_study_go"):
            study_utils.reset(user, parts)
            st.success("Done.")
    with st.expander("🧠 Forget what Jarvis learned about me"):
        if st.checkbox("Yes, erase all learned facts", key="dz_facts") and st.button("Forget everything", key="dz_facts_go"):
            brain_utils.save_facts(user, [])
            st.success("Done.")
    with st.expander("✅ Clear tasks & reminders"):
        if st.checkbox("Yes, clear all my tasks and reminders", key="dz_tasks") and st.button("Clear them", key="dz_tasks_go"):
            for path in (time_utils.TASKS_FILE, time_utils.REMINDERS_FILE):
                data = time_utils._read(path, {})
                data.pop(user, None)
                time_utils._write(path, data)
            st.success("Cleared.")
    with st.expander("📋 Reset the shared daily timetable"):
        st.caption("The timetable is shared by all users.")
        if st.checkbox("Yes, empty the shared timetable", key="dz_tt") and st.button("Empty timetable", key="dz_tt_go"):
            time_utils.save_timetable([])
            st.success("Timetable emptied.")
    with st.expander("⚙️ Reset my settings to defaults"):
        if st.checkbox("Yes, reset my settings", key="dz_set") and st.button("Reset settings", key="dz_set_go"):
            st.session_state.settings = dict(DEFAULTS)
            save_user_settings(user, dict(DEFAULTS))
            st.rerun()


# =============================== DIAGNOSTICS ===============================
def render_diagnostics(s):
    """One screen that tells you WHICH feature is not working and how to fix it."""
    import importlib.util
    import shutil
    import device_control as dc
    from data_paths import abs_dir
    rows = []

    def add(name, ok, detail, fix=""):
        rows.append({"Check": name, "Status": "✅" if ok else "❌", "Details": detail, "Fix": "" if ok else fix})
    envp = env_utils.env_path()
    add(".env file", envp.exists(), str(envp), "Create a file named .env next to Jarvis.py (see .env.example)")
    add("GROQ_API_KEY", bool(os.environ.get("GROQ_API_KEY")), env_utils.mask(os.environ.get("GROQ_API_KEY", "")), "Paste it in .env or Control Panel → API Keys, then Reload .env")
    add("ELEVENLABS_API_KEY", eleven_ready(), env_utils.mask(os.environ.get("ELEVENLABS_API_KEY", "")), "Optional - realistic voice. Add it, then Reload .env")
    add("ElevenLabs voice ID", bool(s.get("eleven_voice_id") or os.environ.get("ELEVENLABS_VOICE_ID")), s.get("eleven_voice_id") or os.environ.get("ELEVENLABS_VOICE_ID") or "default voice (Rachel)",
        "Optional - copy the ID from elevenlabs.io → Voices")
    add("Voice engine in use", True, effective_engine(s))
    for mod, why in [("cryptography", "encrypts chat history"), ("fpdf", "PDF export"), ("pypdf", "read PDFs"), ("PIL", "image branding / screenshots"),
                     ("pyautogui", "PC volume/media/typing (local only)"), ("psutil", "CPU/RAM/battery (local only)")]:
        add(f"python: {mod}", importlib.util.find_spec(mod) is not None, why, f"pip install {'pillow' if mod == 'PIL' else 'fpdf2' if mod == 'fpdf' else mod}")
    add("PC control (JARVIS_LOCAL=1)", dc.pc_enabled(), "ON" if dc.pc_enabled() else "OFF - normal when running in the cloud", "Run Jarvis on your PC with start_on_pc.bat / .sh")
    add("adb (Android control)", bool(dc.adb_path()), dc.adb_path() or "not found", "Install Android platform-tools and add adb to PATH")
    add("SMTP email", all(os.environ.get(k) for k in ("JARVIS_SMTP_HOST", "JARVIS_SMTP_USER", "JARVIS_SMTP_PASS")), "configured" if os.environ.get("JARVIS_SMTP_USER") else "not set",
        "Fill JARVIS_SMTP_* in .env (Gmail needs an App Password)")
    try:
        probe = os.path.join(abs_dir(), ".write_test")
        open(probe, "w").write("x")
        os.remove(probe)
        add("Data folder writable", True, abs_dir())
    except Exception as e:
        add("Data folder writable", False, str(e), "Check folder permissions")
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption("Browser permissions (microphone, notifications, pop-ups) can't be checked from here - allow them for this site in your browser's address-bar menu.")
    if st.button("▶️ Run live tests (Groq · ElevenLabs · Internet)", type="primary"):
        live = []
        try:
            from settings_utils import get_client
            n = len(list(get_client(s, os.environ.get("GROQ_API_KEY", "")).models.list().data))
            live.append(("Groq / chat endpoint", True, f"reachable, {n} models"))
        except Exception as e:
            live.append(("Groq / chat endpoint", False, f"{str(e)[:120]} → check the key, endpoint and model in Control Panel"))
        if eleven_ready():
            ok, msg, _a = eleven_test(s)
            live.append(("ElevenLabs", ok, msg))
        try:
            from web_tools import get_weather_data
            w = get_weather_data(s["weather_city"])
            live.append(("Internet / weather", bool(w.get("ok")), w.get("short", "")))
        except Exception as e:
            live.append(("Internet / weather", False, str(e)))
        for name, ok, msg in live:
            (st.success if ok else st.error)(f"**{name}** - {msg}")


# =============================== CONTROL PANEL ===============================
def render_control_panel():
    s = get_settings()
    user = st.session_state.current_user
    st.subheader("🎛️ Control Panel")
    new = dict(s)
    t_voice, t_keys, t_diag, t_model, t_behave, t_alerts, t_mem, t_look, t_acc = st.tabs(["🔊 Voice", "🔑 API Keys", "🩺 Diagnostics", "🧠 Model", "⚙️ Behaviour", "📧 Alerts", "🧠 Memory", "🎨 Look", "🔐 Account"])
    with t_voice:
        new["tts_enabled"] = st.toggle("Speak replies", value=s["tts_enabled"], key="w_tts_enabled")
        new["tts_engine"] = st.selectbox("Speech engine", TTS_ENGINES, index=TTS_ENGINES.index(s["tts_engine"]), key="w_tts_engine")
        st.caption(f"🔈 Voice in use right now: **{effective_engine(new)}**")
        if new["tts_engine"].startswith(("ElevenLabs", "Auto")):
            st.caption("🎙️ ElevenLabs " + ("key found ✅" if eleven_ready() else "key missing ❌ - add it in the **API Keys** tab or your .env file"))
            if st.button("🔄 Load my ElevenLabs voices", disabled=not eleven_ready()):
                try:
                    st.session_state.eleven_list = eleven_voices()
                except Exception as e:
                    st.error(f"Could not load voices: {e}")
            vl = st.session_state.get("eleven_list", [])
            if vl:
                names = [n for n, _ in vl]
                cur = next((i for i, (_, vid) in enumerate(vl) if vid == s["eleven_voice_id"]), 0)
                pick = st.selectbox("Voice", names, index=cur, key="w_eleven_pick")
                new["eleven_voice_id"] = dict(vl)[pick]
            else:
                new["eleven_voice_id"] = st.text_input("Voice ID (from elevenlabs.io → Voices)", s["eleven_voice_id"], key="w_eleven_id",
                                                       placeholder="blank = default voice (Rachel)")
            models = ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"]
            new["eleven_model"] = st.selectbox("Model", models, index=models.index(s["eleven_model"]) if s["eleven_model"] in models else 0, key="w_eleven_model",
                                               help="Flash = fastest & cheapest. Multilingual v2 = most natural.")
            new["eleven_stability"] = st.slider("Stability", 0.0, 1.0, float(s["eleven_stability"]), 0.05, key="w_eleven_stab")
            new["eleven_similarity"] = st.slider("Similarity", 0.0, 1.0, float(s["eleven_similarity"]), 0.05, key="w_eleven_sim")
            new["eleven_max_chars"] = st.slider("Max characters spoken per reply (saves credits)", 100, 1500, int(s["eleven_max_chars"]), 50, key="w_eleven_max")
            if st.button("🔊 Test ElevenLabs now", type="primary"):
                ok_, msg_, audio_ = eleven_test({**s, **new})
                (st.success if ok_ else st.error)(msg_)
                if audio_:
                    st.audio(audio_, format="audio/mp3")
        new["tts_rate"] = st.slider("Voice speed", 0.5, 2.0, float(s["tts_rate"]), 0.05, key="w_tts_rate")
        new["tts_pitch"] = st.slider("Voice pitch", 0.5, 2.0, float(s["tts_pitch"]), 0.05, key="w_tts_pitch",
                                     help="Browser voices only - pyttsx3 has no pitch control.")
        new["tts_volume"] = st.slider("Volume", 0.0, 1.0, float(s["tts_volume"]), 0.05, key="w_tts_volume")
        new["tts_voice_pref"] = st.selectbox("Voice style", VOICE_PREFS, index=VOICE_PREFS.index(s["tts_voice_pref"]), key="w_voice_pref")
        new["tts_voice_name"] = st.text_input("Exact voice name (optional)", s["tts_voice_name"], key="w_voice_name",
                                              placeholder="e.g. Google UK English Male")
        if st.button("▶️ Test voice"):
            st.session_state.settings = new
            speak_and_notify("Systems online. All voice parameters nominal.", force=True)
        st.markdown("**Wake word**")
        new["wake_word"] = st.toggle("Hands-free wake word", value=s["wake_word"], key="w_wake", help="Chrome/Edge. Say the phrase, then your command.")
        new["wake_phrase"] = st.text_input("Wake phrase", s["wake_phrase"], key="w_wake_phrase")
        langs = ["en-IN", "en-US", "en-GB", "hi-IN"]
        new["stt_lang"] = st.selectbox("Listening language", langs, index=langs.index(s["stt_lang"]), key="w_stt_lang")
        st.markdown("**👏 Double-clap trigger**")
        new["clap_enabled"] = st.toggle("Clap twice to wake Jarvis (needs microphone permission)", value=s["clap_enabled"], key="w_clap")
        new["clap_command"] = st.text_input("When I clap twice, tell Jarvis…", s["clap_command"], key="w_clapcmd", help="Try: turn on the lights")
        new["clap_sensitivity"] = st.slider("Clap sensitivity", 1, 10, int(s["clap_sensitivity"]), key="w_clapsens")
    with t_keys:
        st.caption(f"Keys are stored in your **.env** file (`{env_utils.env_path()}`) - never in the chat database. Real environment variables / "
                   "Codespaces secrets override the file.")
        is_admin = has_permission(st.session_state.get("role", ""), "admin")
        if st.button("🔄 Reload .env now"):
            loaded = env_utils.load_env(override=True)
            st.success(f"Read {len(loaded)} value(s) from {env_utils.env_path()}")
            st.rerun()
        for name, desc in env_utils.KNOWN_KEYS:
            val = os.environ.get(name, "")
            c1, c2 = st.columns([2, 3])
            c1.markdown(f"**{name}**  \n<small>{desc}</small>", unsafe_allow_html=True)
            c2.markdown(("✅ " if val else "❌ ") + (env_utils.mask(val) if "KEY" in name or "PASS" in name else (val or "not set")))
            if is_admin:
                x, y = st.columns([4, 1])
                nv = x.text_input(f"New value for {name}", type="password" if ("KEY" in name or "PASS" in name) else "default", key=f"envin_{name}",
                                  label_visibility="collapsed", placeholder="paste new value…")
                if y.button("Save", key=f"envsave_{name}") and nv.strip():
                    env_utils.set_key(name, nv.strip())
                    audit_log("env_key_set", user=user, detail=name)
                    st.success(f"{name} saved.")
                    st.rerun()
        if not is_admin:
            st.info("Only an admin can change API keys.")
    with t_diag:
        render_diagnostics(s)
    with t_model:
        eps = list(ENDPOINTS)
        new["endpoint"] = ep = st.selectbox("LLM endpoint", eps, index=eps.index(s["endpoint"]), key="w_endpoint")
        if ep == "Custom":
            new["custom_base_url"] = st.text_input("Base URL (OpenAI-compatible)", s["custom_base_url"], key="w_base")
            new["custom_model"] = st.text_input("Model ID", s["custom_model"], key="w_cmodel")
        else:
            models = ENDPOINTS[ep]["models"]
            new["model"] = st.selectbox("Model", models, index=models.index(s["model"]) if s["model"] in models else 0, key=f"w_model_{ep}")
            new["custom_model"] = st.text_input("…or any model ID (overrides)", s["custom_model"], key="w_cmodel2")
        new["temperature"] = st.slider("Creativity (temperature)", 0.0, 1.5, float(s["temperature"]), 0.05, key="w_temp")
        new["memory_window"] = st.slider("Messages remembered per reply", 4, 40, int(s["memory_window"]), 2, key="w_mem")
    with t_behave:
        modes = ["Off", "Smart", "Always"]
        new["web_mode"] = st.select_slider("Internet access", modes, value=s["web_mode"] if s["web_mode"] in modes else "Smart", key="w_webmode",
                                           help="Smart = search for time-sensitive questions. Always = search every question (slower, freshest).")
        am = ["Off", "Auto", "Always"]
        new["agent_mode"] = st.select_slider("Agent mode (Jarvis plans & uses tools before answering)", am, value=s["agent_mode"] if s["agent_mode"] in am else "Auto",
                                             key="w_agent", help="Auto = for real questions. Always = every message (smarter, a little slower).")
        new["learn_facts"] = st.toggle("Learn about me from our chats (goals, weak topics)", value=s["learn_facts"], key="w_learn")
        new["long_term_recall"] = st.toggle("Recall past chats from the .txt log", value=s["long_term_recall"], key="w_recall")
        new["live_alerts"] = st.toggle("Live schedule alerts (check every 30s)", value=s["live_alerts"], key="w_live")
        new["weather_city"] = st.text_input("Weather city", s["weather_city"], key="w_city")
        styles = list(STYLES)
        new["image_style"] = st.selectbox("Default image style", styles, index=styles.index(s["image_style"]) if s["image_style"] in styles else 0, key="w_imgstyle")
        new["auto_open_links"] = st.toggle("Try to open links I ask for automatically (also shown as tap buttons)", value=s["auto_open_links"], key="w_autoopen")
        new["image_brand"] = st.toggle("Stamp 'JARVIS AI' on generated images", value=s["image_brand"], key="w_brand")
    with t_alerts:
        st.caption("A background thread emails you even when this tab is closed (the server must be awake). Needs the SMTP env vars.")
        new["email_alerts"] = st.toggle("Email me schedule, study-plan & reminder alerts", value=s["email_alerts"], key="w_email_on")
        new["email_routine"] = st.toggle("Also email my daily routine (wake up, dinner, sleep, extra reminders)", value=s["email_routine"], key="w_email_routine")
        new["alert_email"] = st.text_input("Send alerts to", s["alert_email"], key="w_email_to", placeholder="you@gmail.com")
        t = st.time_input("Daily exam digest at", datetime.strptime(s["exam_digest_time"], "%H:%M").time(), key="w_digest",
                          help="One email every morning: upcoming exams, chapters left, today's study plan.")
        new["exam_digest_time"] = t.strftime("%H:%M")
        if st.button("📨 Send test email"):
            ok = send_reply_email(new["alert_email"], "Jarvis test", "Email alerts are working. 🚀") if new["alert_email"] else False
            (st.success if ok else st.error)(email_utils.LAST_STATUS or "Enter an email address first.")
    with t_mem:
        st.caption("What Jarvis has learned about you from chatting. He uses it to teach better - delete anything that is wrong.")
        facts = brain_utils.load_facts(user)
        for i, f in enumerate(facts):
            a, b = st.columns([9, 1])
            a.markdown(f"- {f}")
            if b.button("✕", key=f"fact_{i}"):
                brain_utils.delete_fact(user, i)
                st.rerun()
        if not facts:
            st.info("Nothing learned yet - it fills in as we talk.")
        st.caption("🗞️ A fresh Daily Brief (news + a new lesson from your syllabus) is built once a day - ask for it with the chip or say *daily brief*.")
    with t_look:
        themes = list(PALETTES)
        new["theme"] = st.selectbox("Theme", themes, index=themes.index(s["theme"]) if s["theme"] in themes else 0, key="w_theme")
        from realtime_ui import ORB_STYLES
        new["orb_style"] = st.selectbox("Realtime Orb style", ORB_STYLES, index=ORB_STYLES.index(s["orb_style"]) if s["orb_style"] in ORB_STYLES else 0, key="w_orbstyle")
        oc = ["Gold", "Cyan", "Magenta", "Theme"]
        new["orb_color"] = st.selectbox("Realtime Orb colour", oc, index=oc.index(s["orb_color"]) if s["orb_color"] in oc else 0, key="w_orbcolor")
    with t_acc:
        st.markdown("🔒 **History encryption:** " + ("active" if encryption_active() else "⚠️ off - `pip install cryptography`, then restart"))
        with st.form("pw_form", clear_on_submit=True):
            cur, p1, p2 = st.text_input("Current passcode", type="password"), st.text_input("New passcode", type="password"), st.text_input("Confirm", type="password")
            if st.form_submit_button("Change passcode"):
                stored = load_users().get(user, {}).get("password", "")
                if not verify_password(cur, stored):
                    st.error("Current passcode is wrong.")
                elif len(p1) < 6 or p1 != p2:
                    st.error("New passcode must match and be at least 6 characters.")
                else:
                    change_password(user, p1)
                    st.success("Passcode updated.")

    if new != s:
        st.session_state.settings = new
        save_user_settings(user, new)
        if new["theme"] != s["theme"]:
            st.rerun()
        st.toast("Settings saved", icon="✅")
