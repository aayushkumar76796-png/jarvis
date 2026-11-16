"""Slide-out menu (☰ drawer): grouped navigation with live badges, jump-to filter, quick actions, quick add,
recent chats, theme switch, data-saved indicator, Lock Screen and Logout."""
import html as _html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from auth_utils import has_permission
from history_utils import delete_session, list_sessions, load_messages, rename_session, set_pinned
from settings_utils import get_settings, save_user_settings
from theme_utils import PALETTES
from web_tools import get_weather_data

CHAT_MODES = ("Realtime", "Text Chat")

# (group title, [(mode key, icon, label, permission or None)])
GROUPS = [
    ("TALK", [("Realtime", "🌐", "Realtime Orb", None), ("Text Chat", "💬", "Text Chat", "chat")]),
    ("STUDY", [("Study Hub", "📚", "Study Hub", "study"), ("Syllabus", "📖", "My Syllabus", "study"), ("Time Table", "📅", "Time Table", "tasks")]),
    ("TOOLS", [("Action Hub", "🛠️", "Action Hub", "chat"), ("Gallery", "🖼️", "Gallery", "image"), ("Device Control", "🖥️", "Device Control", "chat"),
               ("My Data", "💾", "My Data · chats · backup", None)]),
    ("SYSTEM", [("Control Panel", "🎛️", "Control Panel", None), ("Admin Dashboard", "🛡️", "Admin Dashboard", "admin")]),
]
NAV = [n for _g, items in GROUPS for n in items]


@st.cache_data(ttl=900, show_spinner=False)
def cached_weather(city):
    return get_weather_data(city)


# ---------- callbacks (run before the next script pass) ----------
def go(mode):
    st.session_state.mode = mode


def new_chat():
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.pending_intent = None
    st.session_state.email_draft = None
    if st.session_state.get("mode") not in CHAT_MODES:
        st.session_state.mode = "Text Chat"


def clear_chat():
    """Clears the SCREEN only. The permanent .txt log and saved chats are untouched."""
    st.session_state.messages = []
    st.session_state.session_id = None
    st.session_state.pending_intent = None
    st.session_state.email_draft = None


def load_session(sid):
    st.session_state.messages = load_messages(sid, st.session_state.current_user)
    st.session_state.session_id = sid
    st.session_state.mode = "Text Chat"


def delete_session_cb(sid):
    delete_session(sid, st.session_state.current_user)
    if st.session_state.get("session_id") == sid:
        new_chat()


def rename_cb(sid):
    rename_session(sid, st.session_state.current_user, st.session_state.get(f"rn_{sid}", ""))


def pin_cb(sid, flag):
    set_pinned(sid, st.session_state.current_user, flag)


def _lock():
    st.session_state.locked = True


def _logout():
    st.session_state.update(authenticated=False, locked=False, is_admin=False, current_user="", role="guest",
                            messages=[], session_id=None, mode="Realtime", pending_intent=None)


def _next_theme():
    s = dict(get_settings())
    names = list(PALETTES)
    s["theme"] = names[(names.index(s["theme"]) + 1) % len(names)] if s["theme"] in names else names[0]
    st.session_state.settings = s
    save_user_settings(st.session_state.current_user, s)


def _quick_task():
    from time_utils import add_task
    txt = st.session_state.get("qa_text", "").strip()
    if txt:
        add_task(st.session_state.current_user, txt)
        st.session_state.qa_text = ""
        st.toast("Task added ✅")


def _quick_note():
    import study_utils as su
    txt = st.session_state.get("qa_text", "").strip()
    if txt:
        user = st.session_state.current_user
        d = su.load(user)
        d["notes"].insert(0, {"title": f"Quick note {datetime.now():%d %b %H:%M}", "date": datetime.now().strftime("%Y-%m-%d"), "body": txt})
        su.save(user, d)
        st.session_state.qa_text = ""
        st.toast("Saved to Smart Notes 📝")


# ---------- live badges (cached a few seconds) ----------
@st.cache_data(ttl=20, show_spinner=False)
def _badges(user):
    b, nxt = {}, ""
    try:
        import exam_utils
        import gallery_utils
        import syllabus_utils
        n = len(syllabus_utils.pairs(user))
        b["Syllabus"] = n or ""
        b["Study Hub"] = len(exam_utils.upcoming(user, 30)) or ""
        now = datetime.now()
        cur = now.hour * 60 + now.minute
        items = [i for i in exam_utils.day_items(user) if exam_utils._mins(i["t"]) >= cur]
        b["Time Table"] = len([i for i in items if i["kind"] == "study"]) or ""
        if items:
            nxt = f"{exam_utils._hm(items[0]['t'])} {exam_utils._strip_emoji(items[0]['text'])[:18]}"
        b["Gallery"] = len(gallery_utils.list_images(user)) or ""
        b["My Data"] = len(list_sessions(user, 500)) or ""
    except Exception:
        pass
    return b, nxt


_CLOSE_ON_PICK = """
<script>
(function(){const w=window.parent,d=w.document; if(w.__jvMenu) return; w.__jvMenu=true;
 d.addEventListener('click',e=>{ if(w.innerWidth>=900) return;
   const l=e.target.closest('[class*="st-key-nav_"] button, [class*="st-key-rc_"] button'); if(!l) return;
   setTimeout(()=>{const b=d.querySelector('[data-testid="stSidebarCollapseButton"] button')||d.querySelector('[data-testid="stSidebarCollapseButton"]'); if(b) b.click();},280);});})();
</script>"""


def render_sidebar_menu():
    role = st.session_state.get("role", "normal user")
    user = st.session_state.current_user
    if st.session_state.get("mode") not in [n[0] for n in NAV]:
        st.session_state.mode = "Realtime"
    badges, nxt = _badges(user)

    with st.sidebar:
        st.markdown('<div class="jv-menu-title"><b>⚡</b>SLIDE-OUT MENU</div>', unsafe_allow_html=True)
        try:
            from study_utils import streak_info
            streak = streak_info(user)[0]
        except Exception:
            streak = 0
        pills = f'<span class="jv-pill">🔥 {streak}-day streak</span>'
        if nxt:
            pills += f'<span class="jv-pill">⏰ {_html.escape(nxt)}</span>'
        st.markdown(f'<div class="jv-usercard"><div class="jv-avatar">{_html.escape(user[:1].upper())}</div>'
                    f'<div><b>{_html.escape(user)}</b><small>{role}</small></div></div>{pills}', unsafe_allow_html=True)

        flt = st.text_input("Jump to", key="nav_filter", placeholder="🔎 Jump to…", label_visibility="collapsed").strip().lower()
        n = 0
        with st.container(key="sidenav"):
            for title, items in GROUPS:
                vis = [i for i in items if (i[3] is None or has_permission(role, i[3])) and (not flt or flt in i[2].lower())]
                if not vis:
                    continue
                st.markdown(f'<div class="jv-navgrp">{title}</div>', unsafe_allow_html=True)
                for mode, icon, label, _p in vis:
                    n += 1
                    badge = f"  ·  {badges[mode]}" if badges.get(mode) else ""
                    st.button(f"{icon}  {label}{badge}", key=f"nav_{mode}", on_click=go, args=(mode,), use_container_width=True,
                              type="primary" if st.session_state.mode == mode else "secondary")
            if flt and not n:
                st.caption("No page matches.")

        with st.expander("⚡ Quick add"):
            st.text_input("Type something to save", key="qa_text", placeholder="Revise Trigonometry tomorrow…", label_visibility="collapsed")
            a, b = st.columns(2)
            a.button("✅ Task", on_click=_quick_task, key="qa_task", use_container_width=True)
            b.button("📝 Note", on_click=_quick_note, key="qa_note", use_container_width=True)
        recent = list_sessions(user, 5)
        if recent:
            with st.expander("🕘 Recent chats"):
                for s_ in recent:
                    r1, r2 = st.columns([6, 1])
                    r1.button(("📌 " if s_["pinned"] else "") + s_["title"], key=f"rc_{s_['id']}", on_click=load_session, args=(s_["id"],),
                              use_container_width=True)
                    r2.button("🗑", key=f"rcd_{s_['id']}", on_click=delete_session_cb, args=(s_["id"],), help="Delete this chat")
                st.button("Manage all chats →", on_click=go, args=("My Data",), key="rc_manage", use_container_width=True)

        with st.container(key="side_bottom"):
            try:
                from data_utils import folder_stats
                files, size = folder_stats()
                st.caption(f"💾 {files} files saved · {size / 1024:.0f} KB · jarvis_data/")
            except Exception:
                pass
            st.button("🔒 Lock Screen", on_click=_lock, key="btn_lock", use_container_width=True)
            st.button("🚪 Logout", on_click=_logout, key="btn_logout", use_container_width=True)
            st.button("🧹 Clear screen", on_click=clear_chat, key="btn_clear", use_container_width=True,
                      help="Clears the screen only - your chat .txt log and saved chats stay.")
        components.html(_CLOSE_ON_PICK, height=0)   # on phones the drawer closes after you pick a page
