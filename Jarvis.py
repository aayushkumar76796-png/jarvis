"""JARVIS AI CORE - main entry point.   Run with:  streamlit run Jarvis.py"""
import json
import os
import re
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import mic_recorder

from auth_utils import (ensure_default_admin, get_current_date, get_jarvis_memory, has_permission, normalize_role,
                        verify_user, audit_log)
from admin_ui import render_admin_dashboard
from email_utils import send_reply_email, split_subject_body
import email_utils
from history_utils import (append_message, create_session, import_legacy_txt, make_title, search_history)
import model3d_utils as m3
from gallery_utils import load_image, render_gallery, save_image
from image_generation_and_pdf import (create_image, extract_pdf_text, image_message, render_image_module)
from study_utils import log_study, render_study_hub
from notifier_utils import start_notifier
import transcript_utils as tlog
from realtime_ui import render_command_chips, render_orb
from request_utils import save_request
from settings_utils import active_model, get_client, get_groq_client, get_settings, init_settings, vision_model
import agent_utils
import brain_utils
import device_control as dc
import study_utils as su
from data_utils import render_data_page
from exam_utils import (context_for_llm, days_left, due_plan_items, upcoming, handle_study_command, render_full_plan, render_my_day,
                        today_plan_markdown)
from syllabus_utils import render_syllabus_page
from pages_utils import render_chats_manager, render_control_panel, render_danger_zone
from sidebar_utils import CHAT_MODES, _logout, cached_weather, clear_chat, new_chat, render_sidebar_menu
from speech_utils import (effective_engine, render_clap_trigger, render_notification_permission_button, render_wake_word, speak_and_notify,
                          transcribe_audio)
from system_tools import read_clipboard, take_screenshot
from theme_utils import auto_scroll, hide_sidebar, hud_cards, inject_theme, render_status, render_top_ticker, typing_effect
from time_utils import (_norm_time, add_reminder, add_task, check_and_trigger_timetable, check_due_reminders,
                        delete_reminder, delete_task, get_schedule_summary, handle_conversational_command,
                        list_reminders, list_tasks, load_timetable, now_ist, save_timetable, set_task_done)
from web_tools import extract_urls, fetch_page_text, format_news, format_search_results, get_news, should_search, search_web

st.set_page_config(page_title="Jarvis // Aayush Technology", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

# API keys: prefer env var / Codespaces secret GROQ_API_KEY. This string is only a last-resort fallback.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")     # set it in the .env file (or Control Panel -> API Keys)
USER_LOCATION = "Bengaluru, India"
LOCAL = os.environ.get("JARVIS_LOCAL") == "1"   # set JARVIS_LOCAL=1 when running on your own PC (enables clipboard/screen)

for _k, _v in dict(authenticated=False, current_user="", is_admin=False, role="guest", mode="Realtime",
                   session_id=None, pending_intent=None, last_audio_id=None, used_attach=None, locked=False).items():
    st.session_state.setdefault(_k, _v)
st.session_state.setdefault("messages", [])

registered_users = ensure_default_admin()
inject_theme(get_settings()["theme"])


# =============================== LOGIN GATEWAY ===============================
if not st.session_state.authenticated:
    hide_sidebar()
    st.markdown("<br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="jv-orb-wrap"><div class="jv-orb"></div><div><div class="jv-orb-title">SECURE TERMINAL GATEWAY</div>'
                    '<div class="jv-orb-sub">Authenticate to wake Jarvis.</div></div></div>', unsafe_allow_html=True)
        tab_login, tab_request = st.tabs(["🔑 Login", "📝 Request Access"])
        with tab_login:
            with st.form("login_form"):
                who = st.selectbox("👤 Select Profile", list(registered_users.keys()))
                pw = st.text_input("🔑 Passcode", type="password")
                if st.form_submit_button("⚡ Launch Jarvis", use_container_width=True):
                    ok, msg = verify_user(who, pw)
                    if ok:
                        u = registered_users[who]
                        role = normalize_role(u.get("role"))
                        st.session_state.update(authenticated=True, current_user=who, role=role,
                                                is_admin=(role == "admin"), messages=[], session_id=None, mode="Realtime")
                        init_settings(who)
                        import_legacy_txt(who)
                        tlog.import_legacy(who)
                        st.rerun()
                    else:
                        st.error(msg)
        with tab_request:
            with st.form("access_request_form"):
                rn, re_, rp = st.text_input("Full Name*"), st.text_input("Email*"), st.text_input("Phone Number*")
                ra, rh, rt = st.text_area("Address / Reason"), st.text_input("Hobby"), st.text_input("Target / Goal")
                if st.form_submit_button("Submit Access Request & Email Admin", use_container_width=True):
                    if rn and re_ and rp:
                        save_request({"name": rn, "email": re_, "phone": rp, "address": ra, "hobby": rh, "target": rt,
                                      "date": get_current_date()})
                        admin_mail = os.environ.get("JARVIS_ADMIN_EMAIL") or registered_users.get("Aayush", {}).get("email", "")
                        send_reply_email(admin_mail, "New Jarvis Access Request", f"New request from {rn} ({re_}).")
                        st.success("Request submitted. " + email_utils.LAST_STATUS)
                    else:
                        st.error("Please fill in Name, Email, and Phone number.")
    st.stop()

# =============================== LOCK SCREEN ===============================
if st.session_state.locked:
    hide_sidebar()
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="jv-orb-wrap"><div class="jv-orb"></div><div><div class="jv-orb-title">SCREEN LOCKED</div>'
                    f'<div class="jv-orb-sub">Welcome back, {st.session_state.current_user}. Enter your passcode.</div></div></div>', unsafe_allow_html=True)
        with st.form("unlock_form"):
            pw = st.text_input("🔑 Passcode", type="password")
            u1, u2 = st.columns(2)
            go = u1.form_submit_button("🔓 Unlock", use_container_width=True)
            out = u2.form_submit_button("🚪 Logout", use_container_width=True)
        if go:
            ok, msg = verify_user(st.session_state.current_user, pw)
            if ok:
                st.session_state.locked = False
                st.rerun()
            st.error(msg)
        if out:
            _logout()
            st.rerun()
    st.stop()

# =============================== PROFILE ===============================
user = st.session_state.current_user
role = st.session_state.role
can = lambda perm: has_permission(role, perm)
udata = registered_users.get(user, {})
display_name = "Sir" if udata.get("title_pref", "Sir") == "Sir" else user
school = udata.get("school", "Aayush Technology High")

render_sidebar_menu()
s = get_settings()
client = get_client(s, GROQ_API_KEY)
model = active_model(s)

start_notifier()   # background thread: email alerts even when this tab is closed



def page_header():
    """Title + HUD cards shown on the work pages (Study Hub, Action Hub, Gallery, Time Table, Admin)."""
    st.markdown(f"### ⚡ JARVIS AI CORE // {school} // Welcome, {display_name}")
    hud_cards([("TIME", now_ist().strftime("%I:%M %p")), ("WEATHER", cached_weather(s["weather_city"])["short"]),
               ("DATE", get_current_date()), ("LOCATION", USER_LOCATION), ("MODEL", model.split("/")[-1])])


def check_alerts():
    """Timetable + reminder alerts (toast, voice, browser notification)."""
    for task in check_and_trigger_timetable():
        st.warning(f"⏰ **SCHEDULE:** {task}")
        speak_and_notify(f"{display_name}, schedule alert: {task}", title="Jarvis Schedule")
    for task in check_due_reminders(user):
        st.warning(f"🔔 **REMINDER:** {task}")
        speak_and_notify(f"{display_name}, reminder: {task}", title="Jarvis Reminder")
    if can("study"):
        for task in due_plan_items(user):
            st.info(f"📚 **STUDY PLAN:** {task}")
            speak_and_notify(f"{display_name}, time for: {task}", title="Jarvis Study Plan")


if can("tasks"):
    if s["live_alerts"] and hasattr(st, "fragment"):
        st.fragment(run_every=30)(check_alerts)()   # re-checks every 30s without interrupting a reply
    else:
        check_alerts()


# =============================== CHAT ENGINE ===============================
def parse_turn(text):
    """Turns raw input into (text, action). Slash commands + natural phrases."""
    pending, st.session_state.pending_intent = st.session_state.pending_intent, None
    if pending in ("image", "email", "summarize", "model3d"):
        return {"text": text, "action": pending}
    low = text.lower().strip()
    if low in ("/brief", "/daily") or re.search(r"\b(daily|today'?s)\s+brief\b", low):
        return {"text": "🗞️ Daily brief" + (" (refresh)" if "refresh" in low else ""), "action": "brief"}
    m3x = re.match(r"/3d\s+(.+)", text, re.I) or re.match(
        r"(?:please\s+)?(?:generate|create|make|build|design)(?:\s+me)?(?:\s+an?)?\s+3d\s*(?:model|object|design)?\s*(?:of\s+)?(.+)", text, re.I)
    if m3x:
        return {"text": m3x.group(1), "action": "model3d"}
    m = re.match(r"/image\s+(.+)", text, re.I) or re.match(
        r"(?:please\s+)?(?:generate|create|make|draw)(?:\s+me)?(?:\s+an?)?\s+(?:image|picture|photo|illustration)\s+(?:of\s+)?(.+)", text, re.I)
    if m:
        return {"text": m.group(1), "action": "image"}
    for cmd, act in (("/clipboard", "clipboard"), ("/screenshot", "screen"), ("/screen", "screen"), ("/time", "schedule"),
                     ("/schedule", "schedule")):
        if low == cmd:
            return {"text": text, "action": act}
    for prefix, act in (("/news", "news"), ("/email", "email"), ("/search", "search"), ("/fetch", "fetch")):
        if low.startswith(prefix):
            return {"text": text[len(prefix):].strip(), "action": act, "raw": text}
    return {"text": text, "action": None}


_IMG_MARK = re.compile(r"\[\[img:([\w.\-]+)\]\]")
_3D_MARK = re.compile(r"\[\[3d:([\w.\-]+)\]\]")


def draw_message(m):
    files = _IMG_MARK.findall(m["content"])
    models = _3D_MARK.findall(m["content"])
    text = _3D_MARK.sub("", _IMG_MARK.sub("", m["content"])).strip()
    with st.chat_message(m["role"], avatar="🧑‍💻" if m["role"] == "user" else "🤖"):
        if m.get("image"):
            st.image(m["image"], width=300)
        for f in files:   # generated pictures are re-loaded from the gallery, so they survive refresh & reloaded chats
            data = load_image(user, f)
            st.image(data, width=420) if data else st.caption("🖼️ (image file no longer in gallery)")
        for f in models:   # 3D models are re-loaded from jarvis_data/models3d/
            d3 = m3.load_scene(user, f)
            m3.render_viewer(d3["scene"], 340) if d3 else st.caption("🧊 (3D model file no longer saved)")
        st.markdown(text)


def stream_reply(messages, model_name, slot):
    full = ""
    stream = client.chat.completions.create(model=model_name, messages=messages, temperature=s["temperature"], stream=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            full += chunk.choices[0].delta.content
            slot.markdown(full + " ▌")
    slot.markdown(full)
    return full


def build_system(text, sid):
    parts = [f"[MASTER CORE DIRECTIVE]\n{get_jarvis_memory()}",
             f"You are Jarvis, an advanced AI assistant built by Aayush, talking to {display_name} (username {user}) from {school}. "
             f"Now: {now_ist():%A %d %B %Y, %I:%M %p} IST. Location: {USER_LOCATION}. Be concise and precise.",
             "The app itself handles: reminders ('remind me to X at 5 pm'), tasks ('add task X'), '/image <idea>', '/search', "
             "'/news', '/clipboard', '/screenshot'. If the user wants one of those, tell them the exact phrasing."]
    parts.append("Teaching style: for study questions explain step by step, tie it to the student's syllabus chapters when relevant, "
                 "and end with ONE short check-question. For anything time-sensitive rely ONLY on the live web results provided; "
                 "if there are none, say you are not sure instead of guessing.")
    for block in (brain_utils.facts_block(user), brain_utils.weak_block(user), brain_utils.brief_for_prompt(user)):
        if block:
            parts.append(block)
    if can("study") and context_for_llm(user):
        parts.append("[STUDY CONTEXT - upcoming exams] " + context_for_llm(user))
    if s["long_term_recall"]:   # permanent memory = the "<User> chat with Jarvis.txt" log
        if len(st.session_state.messages) < 4:
            recent = tlog.read_recent(user, 2500)
            if recent:
                parts.append("[YOUR MOST RECENT CONVERSATIONS WITH THIS USER - remember them]\n" + recent)
        hits = tlog.recall(user, text, 4) if len(text.split()) >= 3 else []
        if hits:
            parts.append("[OLDER RELEVANT CONVERSATIONS FROM THE LOG]\n" + "\n".join(hits))
    return "\n\n".join(parts)


def run_device(cmd):
    """Browser actions work everywhere; PC actions need Jarvis running on the PC (see Device Control)."""
    if cmd["type"] == "nav":
        st.session_state.pending_nav = cmd["mode"]
        return f"🧭 Opening **{cmd['label']}**…", []
    if cmd["type"] == "web":
        audit_log("device_web", user=user, detail=cmd["label"])
        if s["auto_open_links"]:
            dc.auto_open(cmd["url"], cmd["label"])
        links = [(cmd["label"], cmd["url"])] + ([("Search Google instead", cmd["alt"])] if cmd.get("alt") else [])
        return f"🌐 **{cmd['label']}**\n\n[▶ Tap to open]({cmd['url']})" + (f" · [🔎 not right? search Google]({cmd['alt']})" if cmd.get("alt") else ""), links
    if not can("device"):
        return "🔒 Your role can't control devices. Ask an admin to make you a power user.", []
    if cmd["type"] != "auto" and not dc.pc_enabled():
        return dc.not_enabled_message(), []
    if cmd["risk"] == "confirm":
        st.session_state.pending_device = cmd
        return f"⚠️ **{cmd['label']}** - please confirm with the buttons below.", []
    ok, msg = dc.execute(cmd, user)
    return ("✅ " if ok else "⚠️ ") + msg, []


def render_suggestions():
    picks = [("📅 What should I study next?", "what to study next"), ("🗓️ Make my study time table", "make a time table"),
             ("🗞️ Today's daily brief", "/brief"),
             ("💡 Teach me a chapter from my syllabus", "Pick the first pending chapter from my study context and teach it simply with one example.")]
    with st.container(key="suggest"):
        cols = st.columns(2)
        for i, (label, prompt) in enumerate(picks):
            if cols[i % 2].button(label, key=f"sg_{i}", use_container_width=True):
                return prompt
    return None


def render_follow_ups(last):
    """Quick actions under the newest answer - makes every reply interactive."""
    clean = re.sub(r"\[\[(?:img|3d):[^\]]+\]\]", "", last).split("\n\n🔗 **Sources:**")[0].strip()
    items = [("💡 Simpler", "Explain that again in much simpler words with an everyday example."),
             ("📝 Example", "Give me one fully solved example on this."),
             ("🎯 Quiz me", "Quiz me on this with 3 short questions. Ask only the first now and wait for my answer."),
             ("🔊 Read", "@read"), ("👍", "@up"), ("👎", "@down")]
    if can("study"):
        items += [("🃏 Cards", "@flash"), ("💾 Save", "@save")]
    with st.container(key="followups"):
        cols = st.columns(len(items))
        for i, (col, (label, p)) in enumerate(zip(cols, items)):
            if not col.button(label, key=f"fu_{i}_{len(st.session_state.messages)}", use_container_width=True):
                continue
            if p == "@read":
                speak_and_notify(clean, force=True)
            elif p in ("@up", "@down"):
                q_ = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
                n_ = brain_utils.record_feedback(user, q_, clean, 1 if p == "@up" else -1)
                st.toast("Thanks - I'll remember what you like 👍" if p == "@up" else "Noted - I'll do better 👎")
                if n_ % 6 == 0:
                    brain_utils.learn_preferences(client, model, user)
            elif p == "@save":
                d = su.load(user)
                d["notes"].insert(0, {"title": f"Chat note {datetime.now():%d %b %H:%M}", "date": datetime.now().strftime("%Y-%m-%d"), "body": clean})
                su.save(user, d)
                st.toast("Saved to Study Hub → Smart Notes", icon="💾")
            elif p == "@flash":
                try:
                    cards = su.make_cards(client, model, clean, 8)
                    su.add_deck(user, f"Chat {datetime.now():%d %b}", cards)
                    st.toast(f"{len(cards)} flashcards created", icon="🃏")
                except Exception as e:
                    st.toast(f"Could not make cards: {e}", icon="⚠️")
            else:
                return p
    return None


def render_chat(mode):
    render_top_ticker(display_name, school, cached_weather(s["weather_city"]), USER_LOCATION)   # fixed, scrolling weather bar
    b1, b2, _sp = st.columns([1.3, 1.6, 4])
    b1.button("＋ New chat", on_click=new_chat, key="top_new", use_container_width=True)
    b2.button("🧹 Clear screen", on_click=clear_chat, key="top_clear", use_container_width=True,
              help="Clears the screen only - your chat .txt log and saved chats are kept.")
    orb_slot = st.empty()
    hud_info = {}
    if mode == "Realtime":
        w_ = cached_weather(s["weather_city"])
        ex_ = upcoming(user, 60) if can("study") else []
        hud_info = {"Time": now_ist().strftime("%I:%M %p"), "Weather": w_.get("short", "-"), "Model": model.split("/")[-1],
                    "Next exam": f"{ex_[0]['name'][:14]} · {days_left(ex_[0])}d" if ex_ else "none",
                    "Voice": effective_engine(s), "Internet": s["web_mode"],
                    "Streak": f"{su.streak_info(user)[0]} days", "Control": "PC ON" if dc.pc_enabled() else "Cloud"}
        render_orb(orb_slot, display_name, "idle", hud_info)
    chat_area = st.container()
    with chat_area:
        for m in st.session_state.messages:
            draw_message(m)
        if not st.session_state.messages:
            st.caption("Ask anything, tap a suggestion, or use a chip below.")

    if st.session_state.get("email_draft") and can("email"):
        with st.expander("📤 Send the drafted email", expanded=True):
            subj, body = split_subject_body(st.session_state.email_draft)
            to = st.text_input("To", key="mail_to")
            subj = st.text_input("Subject", subj, key="mail_subj")
            body = st.text_area("Body", body, height=180, key="mail_body")
            c1, c2 = st.columns(2)
            if c1.button("Send", type="primary", disabled=not to):
                (st.success if send_reply_email(to, subj, body) else st.error)(email_utils.LAST_STATUS)
            if c2.button("Dismiss"):
                st.session_state.email_draft = None
                st.rerun()

    pd = st.session_state.get("pending_device")
    if pd and can("device"):
        with st.container(border=True):
            st.warning(f"Confirm: **{pd['label']}**")
            k1, k2 = st.columns(2)
            if k1.button("✅ Confirm", key="pd_ok", type="primary", use_container_width=True):
                ok_, msg_ = dc.execute(pd, user)
                st.session_state.pending_device = None
                (st.success if ok_ else st.error)(msg_)
            if k2.button("❌ Cancel", key="pd_no", use_container_width=True):
                st.session_state.pending_device = None
                st.rerun()
    follow = None
    msgs_now = st.session_state.messages
    if can("chat"):
        if not msgs_now:
            follow = render_suggestions()
        elif msgs_now[-1]["role"] == "assistant" and msgs_now[-1]["content"].strip():
            follow = render_follow_ups(msgs_now[-1]["content"])
    chip = render_command_chips(can, LOCAL) if can("chat") else None
    c_mic, c_att, c_state = st.columns([1.2, 1, 3])
    with c_mic:
        audio = mic_recorder(start_prompt="🎙️ Speak", stop_prompt="⏹️ Stop", key="jv_mic")
    attachment = None
    with c_att:
        if can("vision"):
            with st.popover("📎 Attach"):
                up = st.file_uploader("Image, PDF or text file", type=["png", "jpg", "jpeg", "pdf", "txt", "md", "csv"], key="attach_file")
            if up is None:
                st.session_state.used_attach = None
            elif (up.name, up.size) != st.session_state.used_attach:
                attachment = up
    with c_state:
        status_slot = st.empty()
        if attachment:
            st.caption(f"📎 {attachment.name} will be sent with your next message")
        if st.session_state.pending_intent:
            label = {"image": "🎨 Describe the image", "email": "✉️ Describe the email",
                     "summarize": "📋 Paste the text to summarize", "model3d": "🧊 Describe the 3D object"}[st.session_state.pending_intent]
            st.info(f"{label} - your next message is used for it.")
            st.button("Cancel", on_click=lambda: st.session_state.update(pending_intent=None))
        else:
            render_status(status_slot, "idle")

    render_wake_word(s["wake_word"], s["wake_phrase"], s["stt_lang"])
    render_clap_trigger(s["clap_enabled"], s["clap_command"], s["clap_sensitivity"])
    typed = st.chat_input("Message Jarvis…  (/image · /search · /news · /clipboard · /screenshot)") if can("chat") else None

    # ---- decide what to run ----
    turn = None
    if typed:
        turn = parse_turn(typed)
        if attachment and not typed.strip():
            turn["text"] = "Analyze this file."
    elif audio and audio.get("id") != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio.get("id")
        render_status(status_slot, "transcribing")
        try:
            spoken = transcribe_audio(get_groq_client(GROQ_API_KEY), audio["bytes"], language=s["stt_lang"][:2])
            if spoken.strip():
                turn = parse_turn(spoken.strip())
        except Exception as e:
            render_status(status_slot, "error", f"Transcription error: {str(e)[:80]}")
    elif chip:
        if chip in ("image", "email", "model3d") or (chip == "clipboard" and not LOCAL):
            st.session_state.pending_intent = "summarize" if chip == "clipboard" else chip
            st.rerun()
        label = {"clipboard": "📋 Summarize my clipboard", "schedule": "🕒 Check time & schedule",
                 "news": "📰 Latest news briefing", "screen": "🖥️ Analyze my screen",
                 "quiz": "🧠 Quiz me", "brief": "🗞️ Daily brief", "next": "What should I study next?"}[chip]
        turn = {"text": label, "action": None if chip == "next" else chip}
    elif follow:
        turn = parse_turn(follow)
    if not turn:
        return

    action, text = turn["action"], turn["text"]
    sid = st.session_state.session_id
    if sid is None:
        sid = st.session_state.session_id = create_session(user, make_title(text))
    window = int(s["memory_window"])
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages][-window:]

    note = f"\n\n📎 *{attachment.name}*" if attachment else ""
    user_msg = {"role": "user", "content": (turn.get("raw") or text) + note}
    if attachment and attachment.type and attachment.type.startswith("image/"):
        user_msg["image"] = attachment.getvalue()
    st.session_state.messages.append(user_msg)
    append_message(sid, "user", user_msg["content"])
    tlog.append_turn(user, "user", user_msg["content"])

    with chat_area:
        draw_message(user_msg)
        auto_scroll(40)
        with st.chat_message("assistant", avatar="🤖"):
            status, body = st.empty(), st.empty()

            def state(name, label=None):
                render_status(status, name, label)
                if mode == "Realtime":
                    render_orb(orb_slot, display_name, name, hud_info)

            reply, gen_img, local, llm_text, context, image, img_file, srcs = "", None, None, text, "", None, "", []
            dev_links, used_agent, steps, model_file, scene3d = [], False, [], "", None
            try:
                state("thinking")
                # ---- attachments ----
                if attachment:
                    state("reading")
                    data = attachment.getvalue()
                    if attachment.type and attachment.type.startswith("image/"):
                        image = (data, attachment.type)
                    elif attachment.type == "application/pdf":
                        context += f"[Attached PDF: {attachment.name}]\n{extract_pdf_text(data)}\n"
                    else:
                        context += f"[Attached file: {attachment.name}]\n{data.decode('utf-8', errors='ignore')[:12000]}\n"
                    st.session_state.used_attach = (attachment.name, attachment.size)

                # ---- actions ----
                if action == "image":
                    state("imaging")
                    gen_img, final_prompt = create_image(client, model, text, s["image_style"])
                    img_file, gen_img = save_image(user, gen_img, text, final_prompt, s["image_style"], sid, stamp=s["image_brand"])
                    local = f"Here is your image, {display_name}. *Style: {s['image_style']}*\n\n**Prompt used:** {final_prompt}"
                elif action == "model3d":
                    state("imaging", "Designing your 3D model")
                    scene3d = m3.generate_scene(client, model, text)
                    model_file = m3.save_scene(user, text, scene3d)
                    local = f"Here is your 3D model: **{scene3d['title']}** ({len(scene3d['parts'])} parts) - drag to rotate, scroll to zoom."
                elif action == "schedule":
                    local = get_schedule_summary(user) + ("\n\n" + today_plan_markdown(user) if can("study") else "")
                elif action == "clipboard":
                    ok, res = read_clipboard()
                    if ok:
                        llm_text = "Summarize this clipboard content with the key points:\n\n" + res
                    else:
                        local = res
                elif action == "screen":
                    state("reading", "Capturing screen")
                    ok, res = take_screenshot()
                    if ok:
                        image, llm_text = (res, "image/png"), "Describe what is on my screen and point out anything important or any errors."
                        image = (res, "image/png")
                    else:
                        local = res
                elif action == "news":
                    state("searching", "Fetching headlines")
                    llm_text = f"Give me a short briefing of these headlines{' about ' + text if text else ''}:\n{format_news(get_news(text))}"
                elif action == "brief":
                    state("searching", "Gathering today's news & lesson")
                    local = brain_utils.daily_brief(user, client, model, force="refresh" in text.lower())
                elif action == "summarize":
                    llm_text = "Summarize the following text clearly, with key points:\n\n" + text
                elif action == "quiz":
                    llm_text = "Quiz me: ask 3 short Class 10 questions (maths/physics mix), one at a time. Ask only the first now and wait for my answer."
                elif action == "email":
                    llm_text = "Draft a professional email for this request. Start with 'Subject: ...' then the body:\n" + text
                elif action in ("search", "fetch") or not action:
                    if not action and local is None and can("chat"):
                        dcmd = dc.parse_device_command(text)             # "open youtube", "volume up", "directions to ..."
                        if dcmd:
                            local, dev_links = run_device(dcmd)
                    if not action and local is None and can("study"):
                        local = handle_study_command(user, text)          # "what to study next" / "make a time table"
                    if not action and local is None and can("study"):
                        local = brain_utils.handle_brain_command(user, text)   # "where am I weak?"
                    if not action and local is None and can("tasks"):
                        local = handle_conversational_command(user, text)
                    if local is None and not action and can("web") and agent_utils.wants_agent(text, s["agent_mode"]):
                        state("thinking", "Planning · choosing tools")
                        a_ctx, a_srcs, steps = agent_utils.gather(client, model, user, text, city=s["weather_city"],
                                                                  on_step=lambda t_, a_: state("searching", f"Using {t_.replace('_', ' ')}…"))
                        if a_ctx:
                            context += a_ctx
                            srcs += a_srcs
                            used_agent = True
                    if local is None and can("web"):
                        if action == "fetch":
                            state("searching", "Reading page")
                            context += "[Web page]\n" + "\n".join(fetch_page_text(u) for u in extract_urls(text) or [text]) + "\n"
                            llm_text = "Summarize this page."
                        else:
                            urls = extract_urls(text)
                            if urls:
                                state("searching", "Reading page")
                                context += "[Web page]\n" + "\n".join(fetch_page_text(u) for u in urls) + "\n"
                            if action == "search" or (not used_agent and should_search(text, s["web_mode"])):
                                state("searching")
                                srcs = search_web(text)
                                context += "[Live web results - cite them by name]\n" + format_search_results(srcs) + "\n"
                                llm_text = text or "Summarize the search results."

                # ---- respond ----
                if local is not None:
                    state("responding")
                    typing_effect(body, local, chunk=max(3, len(local) // 220))
                    reply = local
                else:
                    api_text = llm_text + (("\n\n" + context) if context else "")
                    final = image_message(api_text, image[0], image[1]) if image else {"role": "user", "content": api_text}
                    msgs = [{"role": "system", "content": build_system(text, sid)}] + history + [final]
                    state("responding")
                    reply = stream_reply(msgs, vision_model(s) if image else model, body)
                reply_core = reply
                if srcs and local is None:
                    reply += "\n\n🔗 **Sources:** " + " · ".join(f"[{r['title'][:42]}]({r['url']})" for r in srcs[:3])
                    body.markdown(reply)
                status.empty()
                if steps:
                    with st.expander("🧠 How I worked this out"):
                        for t_, a_, o_ in steps:
                            st.markdown(f"**{t_.replace('_', ' ')}** · `{a_[:80]}`")
                            st.caption(o_[:300])
                for lbl, url in dev_links:
                    st.link_button(f"▶ {lbl}", url)
                if scene3d:
                    m3.render_viewer(scene3d, 380)
                shot = st.session_state.pop("device_image", None)
                if shot:
                    st.image(shot, width=340)
                if gen_img:
                    st.image(gen_img, width=420)
                    st.caption("✅ Saved to your Gallery")
                    st.download_button("⬇️ Download image", gen_img, "jarvis_image.png", "image/png", key=f"dl_{sid}_{len(st.session_state.messages)}")
            except Exception as e:
                state("error")
                st.error(f"Error: {e}")
                return

    stored = reply + (f"\n[[img:{img_file}]]" if img_file else "") + (f"\n[[3d:{model_file}]]" if model_file else "")
    st.session_state.messages.append({"role": "assistant", "content": stored})
    append_message(sid, "assistant", stored)
    tlog.append_turn(user, "assistant", reply + (f"\n[Image saved in gallery: {img_file}]" if img_file else "") + (f"\n[3D model saved: {model_file}]" if model_file else ""))
    if mode == "Realtime":
        render_orb(orb_slot, display_name, "speaking", hud_info)
    if action == "email":
        st.session_state.email_draft = reply
        st.rerun()
    if st.session_state.get("pending_nav"):
        st.session_state.mode = st.session_state.pop("pending_nav")
        st.rerun()
    speak_and_notify(reply_core, title="Jarvis AI Response")
    auto_scroll(3)
    n_user = sum(1 for m in st.session_state.messages if m["role"] == "user")
    if s["learn_facts"] and n_user % 3 == 0 and local is None:   # Jarvis learns about you every few messages
        try:
            brain_utils.learn_from_chat(client, model, user, st.session_state.messages)
        except Exception:
            pass


# =============================== TIME TABLE PAGE ===============================
def pomodoro(end_ms):
    components.html("""
    <div style="font-family:'IBM Plex Mono',monospace;color:#e8f4ff;background:#120a24;border:1px solid #00e5ff55;border-radius:14px;padding:14px;text-align:center">
      <div id="t" style="font-size:42px;color:#00e5ff;text-shadow:0 0 16px #00e5ff88">--:--</div><div id="m" style="color:#8a93b8">focus session</div></div>
    <script>
    const end=__END__, t=document.getElementById('t'), m=document.getElementById('m');
    const iv=setInterval(()=>{const left=Math.max(0,end-Date.now()), s=Math.floor(left/1000);
      t.textContent=String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');
      if(left<=0){clearInterval(iv);m.textContent='Session complete - take a break!';
        try{const c=new AudioContext(),o=c.createOscillator();o.connect(c.destination);o.frequency.value=880;o.start();setTimeout(()=>o.stop(),700);}catch(e){}
        try{speechSynthesis.speak(new SpeechSynthesisUtterance('Focus session complete. Well done.'));}catch(e){}
        if('Notification' in window&&Notification.permission==='granted') new Notification('Jarvis Focus Timer',{body:'Session complete!'});}
    },250);
    </script>""".replace("__END__", str(int(end_ms))), height=130)


def render_time_page():
    st.subheader("📅 Schedule, Tasks & Focus")
    t_day, t_sched, t_plan, t_tasks, t_rem, t_focus = st.tabs(["🗓️ My Day", "📋 Daily Schedule", "🧠 Study Planner", "✅ Tasks", "⏰ Reminders", "⏱️ Focus Timer"])
    with t_day:
        render_my_day(user)
    with t_sched:
        sched = load_timetable()
        for i, item in enumerate(sched):
            a, b = st.columns([6, 1])
            a.markdown(f"**{item['time']}** - {item['message']} {'🔔' if item.get('notify') == 'Yes' else ''}"
                       f"{' 📧' if item.get('notify') == 'Yes' and item.get('email', True) else ''}")
            if b.button("🗑", key=f"del_tt_{i}"):
                sched.pop(i)
                save_timetable(sched)
                st.rerun()
        with st.form("add_timetable_form"):
            t = st.text_input("Time (e.g., 07:45 AM)")
            n = st.selectbox("Notification", ["Yes", "No"])
            msg = st.text_input("What to notify", value="Complete study task")
            em = st.checkbox("📧 Also email me at this time (turn on in Control Panel → Alerts)", value=True)
            if st.form_submit_button("➕ Add Schedule"):
                if _norm_time(t):
                    sched.append({"time": t.strip().upper(), "notify": n, "message": msg, "email": em})
                    save_timetable(sched)
                    st.rerun()
                else:
                    st.error("Use a time like 07:45 AM or 19:30.")
    with t_plan:
        render_full_plan(user)
    with t_tasks:
        with st.form("add_task", clear_on_submit=True):
            txt = st.text_input("New task")
            if st.form_submit_button("➕ Add task") and txt:
                add_task(user, txt)
                st.rerun()
        for tk in list_tasks(user, include_done=True):
            a, b = st.columns([6, 1])
            if a.checkbox(tk["text"], value=tk["done"], key=f"tk_{tk['id']}") != tk["done"]:
                set_task_done(user, tk["id"], not tk["done"])
                st.rerun()
            if b.button("🗑", key=f"deltk_{tk['id']}"):
                delete_task(user, tk["id"])
                st.rerun()
        st.caption("Tip: tell Jarvis *add task finish algebra homework* or *show my tasks*.")
    with t_rem:
        with st.form("add_rem", clear_on_submit=True):
            txt = st.text_input("Remind me to…")
            d, tm = st.columns(2)
            day, clock = d.date_input("Date", now_ist().date()), tm.time_input("Time", now_ist().time().replace(second=0, microsecond=0))
            if st.form_submit_button("⏰ Set reminder") and txt:
                add_reminder(user, txt, datetime.combine(day, clock))
                st.rerun()
        for r in list_reminders(user):
            a, b = st.columns([6, 1])
            a.markdown(f"**{datetime.fromisoformat(r['when']):%d %b, %I:%M %p}** - {r['text']}")
            if b.button("🗑", key=f"delr_{r['id']}"):
                delete_reminder(user, r["id"])
                st.rerun()
        st.caption("Tip: say *remind me to call mom at 6 pm* or *in 20 minutes*. Alerts fire when the page refreshes (turn on Live alerts in the sidebar).")
    with t_focus:
        render_notification_permission_button()
        mins = st.number_input("Study duration (minutes)", 1, 120, 25)
        c1, c2 = st.columns(2)
        if c1.button("🚀 Start session", use_container_width=True):
            st.session_state.pomo_end = (now_ist().timestamp() + mins * 60) * 1000
            st.session_state.pomo_mins = int(mins)
        if c2.button("■ Stop", use_container_width=True):
            st.session_state.pomo_end = None
        if st.session_state.get("pomo_end"):
            pomodoro(st.session_state.pomo_end)
            subj = st.text_input("Subject you're studying", "Maths", key="pomo_subj")
            if st.button(f"✅ Finished - log {st.session_state.get('pomo_mins', 25)} min to my streak", use_container_width=True):
                log_study(user, st.session_state.get("pomo_mins", 25), subj)
                st.session_state.pomo_end = None
                st.success("Logged! Check Study Hub → Progress.")


# =============================== ROUTER ===============================
mode = st.session_state.mode
HUD_MODES = ("Study Hub", "Syllabus", "Action Hub", "Gallery", "Time Table", "Admin Dashboard")
if mode in HUD_MODES:
    page_header()

if mode in CHAT_MODES:
    render_chat(mode)
elif mode == "Study Hub":
    if can("study"):
        render_study_hub(user, client, model, vision_model(s))
    else:
        st.warning("Your role does not include the Study Hub.")
elif mode == "Syllabus":
    if can("study"):
        render_syllabus_page(user, client, model, vision_model(s))
    else:
        st.warning("Your role does not include the Study Hub.")
elif mode == "Gallery":
    if can("image"):
        t_img, t_3d = st.tabs(["🖼️ Images", "🧊 3D models"])
        with t_img:
            render_gallery(user)
        with t_3d:
            m3.render_models_page(user)
    else:
        st.warning("Your role cannot view the gallery.")
elif mode == "Action Hub":
    render_image_module(client=client, model=model, vision_model=vision_model(s), messages=st.session_state.messages,
                        perms=can, username=user, stamp=s["image_brand"])
elif mode == "Time Table":
    if can("tasks"):
        render_time_page()
    else:
        st.warning("Your role does not include schedules and tasks.")
elif mode == "Admin Dashboard":
    if can("admin"):
        render_admin_dashboard()
    else:
        st.warning("Admin access required.")
elif mode == "My Data":
    t_data, t_chats, t_danger = st.tabs(["💾 Data & Backup", "💬 Chats", "🧨 Danger Zone"])
    with t_data:
        render_data_page(user)
    with t_chats:
        render_chats_manager()
    with t_danger:
        render_danger_zone()
elif mode == "Device Control":
    dc.render_device_page(user, role)
elif mode == "Control Panel":
    render_control_panel()
