"""Visual layer: glowing dark themes, status pills, HUD cards, typing effect."""
import time

import streamlit as st
import streamlit.components.v1 as components

PALETTES = {
    # name: bg, surface, border, text, muted, accent, accent2
    "Cyberpunk Neon": dict(bg="#07060d", bg2="#120a24", surface="rgba(24,16,48,.72)", border="rgba(0,229,255,.28)",
                           text="#e8f4ff", muted="#8a93b8", accent="#00e5ff", accent2="#ff2bd6", glow="0,229,255", glow2="255,43,214"),
    "Minimal Dark": dict(bg="#0d0f12", bg2="#14171c", surface="rgba(28,32,39,.85)", border="rgba(255,255,255,.10)",
                         text="#e9ecf1", muted="#8b93a1", accent="#7c9cff", accent2="#9aa7c7", glow="124,156,255", glow2="154,167,199"),
    "Stark Gold": dict(bg="#040302", bg2="#120a04", surface="rgba(26,15,6,.74)", border="rgba(255,154,31,.32)",
                       text="#fff1de", muted="#b89570", accent="#ff9a1f", accent2="#ff5a1a", glow="255,154,31", glow2="255,90,26"),
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=IBM+Plex+Sans:wght@300;400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--j-bg:__bg;--j-bg2:__bg2;--j-surface:__surface;--j-border:__border;--j-text:__text;--j-muted:__muted;
--j-accent:__accent;--j-accent2:__accent2;--j-glow:__glow;--j-glow2:__glow2;}
html,body,[data-testid="stAppViewContainer"],.stApp{background:radial-gradient(1200px 600px at 85% -10%,rgba(var(--j-glow),.10),transparent 60%),
 radial-gradient(900px 500px at -10% 110%,rgba(var(--j-glow2),.08),transparent 60%),var(--j-bg)!important;color:var(--j-text);
 font-family:'IBM Plex Sans',system-ui,sans-serif;}
[data-testid="stHeader"]{background:transparent!important}
#MainMenu,footer{visibility:hidden}
h1,h2,h3,h4{font-family:'Chakra Petch',sans-serif!important;letter-spacing:.02em;color:var(--j-text)}
h3{text-shadow:0 0 18px rgba(var(--j-glow),.35)}
.block-container{padding-top:1.6rem;max-width:1100px}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:rgba(var(--j-glow),.35);border-radius:8px}

/* sidebar */
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--j-bg2),var(--j-bg))!important;border-right:1px solid var(--j-border)}
[data-testid="stSidebar"] .stMarkdown h3{font-size:.95rem;color:var(--j-accent)}
[data-testid="stSidebar"] [data-testid="stExpander"]{border:1px solid var(--j-border);border-radius:12px;background:var(--j-surface)}
.jv-brand{display:flex;align-items:center;gap:.6rem;font-family:'Chakra Petch';font-weight:700;font-size:1.25rem;color:var(--j-text)}
.jv-brand i{width:12px;height:12px;border-radius:50%;background:var(--j-accent);box-shadow:0 0 12px var(--j-accent),0 0 28px rgba(var(--j-glow),.6)}

/* buttons */
.stButton>button,.stDownloadButton>button{border-radius:10px;border:1px solid var(--j-border);background:var(--j-surface);
 color:var(--j-text);transition:all .18s ease;backdrop-filter:blur(6px)}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-2px);border-color:var(--j-accent);color:var(--j-accent);
 box-shadow:0 6px 18px rgba(var(--j-glow),.28)}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,var(--j-accent),var(--j-accent2));color:#05050a;border:none;font-weight:600}
.st-key-chips .stButton>button{border-radius:999px;font-size:.8rem;padding:.3rem .6rem;min-height:2.6rem;height:auto}
.st-key-chips .stButton>button p{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.15;text-align:center}
/* thin sidebar navigation */
[data-testid="stSidebar"] .stMarkdown p,[data-testid="stSidebar"] label p,[data-testid="stSidebar"] button p,[data-testid="stSidebar"] small{font-weight:300!important}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.1rem}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:.62rem .8rem;border-radius:10px;border:1px solid transparent;border-left:3px solid transparent;transition:all .15s;width:100%}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:.95rem;letter-spacing:.02em;text-transform:none;font-weight:400!important}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(var(--j-glow),.06)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){border-color:rgba(var(--j-glow),.45);border-left-color:var(--j-accent);background:linear-gradient(90deg,rgba(var(--j-glow),.18),rgba(var(--j-glow),.03))}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:var(--j-accent);font-weight:400!important}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none}
/* slide-out menu */
.jv-menu-title{font-family:'Chakra Petch',sans-serif;font-weight:700;font-size:1.05rem;letter-spacing:.14em;color:var(--j-accent);padding:.2rem 0 .9rem;border-bottom:1px solid var(--j-border);margin-bottom:.8rem;text-shadow:0 0 14px rgba(var(--j-glow),.5)}
.jv-menu-title b{color:var(--j-accent2);margin-right:.35rem}
.st-key-side_bottom{position:sticky;bottom:0;padding:.8rem 0 .4rem;margin-top:1rem;border-top:1px solid var(--j-border);background:var(--j-bg2)}
.st-key-btn_lock button{background:transparent!important;border:1px solid var(--j-accent)!important;color:var(--j-accent)!important;font-weight:500}
.st-key-btn_clear button{background:transparent!important;border:1px dashed var(--j-border)!important;color:var(--j-muted)!important;font-size:.85rem}
.st-key-btn_logout button{background:#ff2b3a!important;border:none!important;color:#fff!important;font-weight:600}
.st-key-btn_logout button:hover{box-shadow:0 6px 18px rgba(255,43,58,.4)!important;color:#fff!important}
/* hamburger + close icons for the slide-out menu */
[data-testid="stSidebarCollapsedControl"] button,[data-testid="stExpandSidebarButton"]{font-size:0!important;border:1px solid var(--j-border);border-radius:10px;background:var(--j-surface)}
[data-testid="stSidebarCollapsedControl"] button *,[data-testid="stExpandSidebarButton"] *{display:none!important}
[data-testid="stSidebarCollapsedControl"] button::after,[data-testid="stExpandSidebarButton"]::after{content:"☰";font-size:1.35rem;color:var(--j-accent);line-height:1}
[data-testid="stSidebarCollapseButton"] button{font-size:0!important}
[data-testid="stSidebarCollapseButton"] button *{display:none!important}
[data-testid="stSidebarCollapseButton"] button::after{content:"✕";font-size:1.2rem;color:var(--j-muted)}
/* fixed moving top bar: title + weather */
.jv-ticker{position:fixed;top:.6rem;left:3.6rem;right:3.8rem;height:2.4rem;overflow:hidden;z-index:999;pointer-events:none;border:1px solid var(--j-border);border-radius:999px;background:var(--j-surface);backdrop-filter:blur(10px);display:flex;align-items:center;box-shadow:0 0 22px rgba(var(--j-glow),.18)}
.jv-ticker-track{display:inline-flex;white-space:nowrap;animation:jv-marquee 46s linear infinite}
.jv-ticker-track span{padding-right:3.2rem;font-size:.86rem;color:var(--j-text)}
.jv-ticker-track b{color:var(--j-accent);font-family:'Chakra Petch',sans-serif;letter-spacing:.06em}
@keyframes jv-marquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.jv-ticker-track{animation:none}}
/* grouped navigation buttons */
.jv-navgrp{font-size:.66rem;letter-spacing:.18em;color:var(--j-muted);margin:.85rem 0 .2rem .2rem}
.st-key-sidenav .stButton>button{justify-content:flex-start;text-align:left;width:100%;border:1px solid transparent;border-left:3px solid transparent;background:transparent;padding:.5rem .8rem;font-size:.93rem;min-height:2.5rem;backdrop-filter:none}
.st-key-sidenav .stButton>button p{text-align:left;font-weight:400!important}
.st-key-sidenav .stButton>button:hover{background:rgba(var(--j-glow),.07);transform:none;box-shadow:none;color:var(--j-text)}
.st-key-sidenav .stButton>button[kind="primary"],.st-key-sidenav .stButton>button[data-testid="stBaseButton-primary"]{background:linear-gradient(90deg,rgba(var(--j-glow),.20),rgba(var(--j-glow),.03));color:var(--j-accent);border:1px solid rgba(var(--j-glow),.45);border-left:3px solid var(--j-accent)}
.st-key-sidenav .stButton>button[kind="primary"] p{font-weight:500!important}
[class*="st-key-rc_"] .stButton>button{justify-content:flex-start;text-align:left;font-size:.82rem;border:none;background:transparent}
/* user card + pills (slide-out menu) */
.jv-usercard{display:flex;align-items:center;gap:.75rem;padding:.7rem .8rem;border:1px solid var(--j-border);border-radius:14px;background:var(--j-surface);margin-bottom:.45rem}
.jv-avatar{width:40px;height:40px;flex:none;border-radius:50%;display:grid;place-items:center;font-family:'Chakra Petch',sans-serif;font-weight:700;color:#05050a;background:linear-gradient(135deg,var(--j-accent),var(--j-accent2));box-shadow:0 0 16px rgba(var(--j-glow),.55)}
.jv-usercard b{display:block;color:var(--j-text);font-weight:500}.jv-usercard small{color:var(--j-muted);font-size:.72rem}
.jv-pill{display:inline-block;padding:.14rem .6rem;border-radius:999px;border:1px solid var(--j-border);font-size:.7rem;color:var(--j-muted);margin:0 .3rem .6rem 0}
/* interactive answers */
.st-key-followups .stButton>button{border-radius:999px;font-size:.78rem;padding:.2rem .4rem;min-height:2.1rem}
.st-key-suggest .stButton>button{text-align:left;min-height:3.2rem;border-radius:14px;background:linear-gradient(135deg,rgba(var(--j-glow),.10),rgba(var(--j-glow2),.06))}
/* chat history rows */
.st-key-hist .stButton>button{text-align:left;justify-content:flex-start;border:none;background:transparent;padding:.3rem .55rem;min-height:2rem;font-size:.85rem}
.st-key-hist .stButton>button p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:300}
.st-key-hist .stButton>button:hover{background:rgba(var(--j-glow),.10);transform:none;box-shadow:none}
.jv-grp{color:var(--j-muted);font-size:.68rem;letter-spacing:.14em;margin:.7rem 0 .15rem;text-transform:uppercase}
/* weather card */
.jv-wx{border:1px solid var(--j-border);background:var(--j-surface);border-radius:14px;padding:.7rem .85rem;margin:.3rem 0 .6rem}
.jv-wx-top{display:flex;align-items:center;gap:.6rem}.jv-wx-ico{font-size:2rem;line-height:1}
.jv-wx-temp{font-family:'IBM Plex Mono',monospace;font-size:1.5rem;color:var(--j-text)}
.jv-wx-city{color:var(--j-muted);font-size:.75rem;letter-spacing:.08em;text-transform:uppercase}
.jv-wx-meta{display:flex;justify-content:space-between;color:var(--j-muted);font-size:.74rem;margin:.45rem 0}
.jv-wx-days{display:grid;grid-template-columns:repeat(3,1fr);gap:.35rem}
.jv-wx-day{text-align:center;border-radius:10px;background:rgba(var(--j-glow),.07);padding:.3rem .1rem;font-size:.72rem;color:var(--j-muted)}
.jv-wx-day b{display:block;color:var(--j-text);font-weight:400;font-family:'IBM Plex Mono',monospace}

/* chat bubbles */
[data-testid="stChatMessage"]{background:var(--j-surface);border:1px solid var(--j-border);border-radius:16px;padding:.9rem 1.1rem;
 margin-bottom:.7rem;backdrop-filter:blur(8px);box-shadow:0 0 0 1px rgba(255,255,255,.02),0 10px 30px rgba(0,0,0,.35)}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"],[data-testid="chatAvatarIcon-user"]){
 background:linear-gradient(135deg,rgba(var(--j-glow),.16),rgba(var(--j-glow2),.10));border-color:rgba(var(--j-glow),.45);margin-left:9%}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"],[data-testid="chatAvatarIcon-assistant"]){
 border-left:3px solid var(--j-accent);margin-right:6%}
[data-testid="stChatInput"]{border:1px solid var(--j-border);border-radius:14px;background:var(--j-surface)}
[data-testid="stChatInput"]:focus-within{border-color:var(--j-accent);box-shadow:0 0 0 1px var(--j-accent),0 0 24px rgba(var(--j-glow),.30)}
[data-testid="stBottom"]>div{background:transparent!important}

/* inputs, tabs */
.stTextInput input,.stTextArea textarea,.stSelectbox [data-baseweb="select"]>div{background:var(--j-surface)!important;border-color:var(--j-border)!important;color:var(--j-text)!important}
.stTabs [data-baseweb="tab-list"]{gap:.3rem;border-bottom:1px solid var(--j-border)}
.stTabs [aria-selected="true"]{color:var(--j-accent)!important}
hr{border-color:var(--j-border)!important}

/* HUD cards */
.jv-hud{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem;margin:.4rem 0 1rem}
.jv-card{border:1px solid var(--j-border);background:var(--j-surface);border-radius:14px;padding:.65rem .9rem;position:relative;overflow:hidden}
.jv-card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(var(--j-accent),var(--j-accent2))}
.jv-card::after{content:"";position:absolute;right:0;bottom:0;width:14px;height:14px;border-right:2px solid var(--j-accent);border-bottom:2px solid var(--j-accent);opacity:.85}
.jv-card small{color:var(--j-muted);font-size:.72rem;letter-spacing:.06em}
.jv-card div{font-family:'IBM Plex Mono',monospace;font-size:1.02rem;color:var(--j-text);margin-top:.1rem;word-break:break-word}

/* status pill */
.jv-status{display:inline-flex;align-items:center;gap:.55rem;padding:.3rem .85rem;border-radius:999px;border:1px solid var(--j-border);
 background:var(--j-surface);font-size:.85rem;color:var(--j-text)}
.jv-status .dot{width:9px;height:9px;border-radius:50%;background:var(--c,var(--j-accent));box-shadow:0 0 10px var(--c,var(--j-accent));animation:jv-pulse 1.2s infinite}
.jv-dots span{animation:jv-blink 1.4s infinite both;font-weight:700}
.jv-dots span:nth-child(2){animation-delay:.2s}.jv-dots span:nth-child(3){animation-delay:.4s}
@keyframes jv-blink{0%,80%,100%{opacity:.2}40%{opacity:1}}
@keyframes jv-pulse{0%,100%{transform:scale(.8);opacity:.7}50%{transform:scale(1.25);opacity:1}}

/* orb */
.jv-orb-wrap{display:flex;align-items:center;gap:1.2rem;margin:.2rem 0 .8rem}
.jv-orb{width:74px;height:74px;flex:none;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff 0,var(--j-accent) 22%,var(--j-accent2) 100%);
 box-shadow:0 0 28px rgba(var(--j-glow),.7),inset 0 0 18px rgba(255,255,255,.35);animation:jv-orb 3s infinite ease-in-out}
.jv-orb.listening{animation-duration:.9s;filter:hue-rotate(40deg)}
.jv-orb.thinking{animation:jv-spin 1.6s linear infinite;filter:saturate(1.6)}
.jv-orb.speaking{animation-duration:.6s}
@keyframes jv-orb{0%,100%{transform:scale(.94);box-shadow:0 0 18px rgba(var(--j-glow),.45)}50%{transform:scale(1.06);box-shadow:0 0 48px rgba(var(--j-glow),.9)}}
@keyframes jv-spin{0%{transform:rotate(0) scale(1)}50%{transform:rotate(180deg) scale(1.08)}100%{transform:rotate(360deg) scale(1)}}
.jv-orb-title{font-family:'Chakra Petch';font-size:1.35rem;font-weight:700;color:var(--j-text)}
.jv-orb-sub{color:var(--j-muted);font-size:.9rem}
@media (prefers-reduced-motion:reduce){.jv-orb,.jv-status .dot,.jv-dots span{animation:none!important}}
@media (max-width:640px){[data-testid="stChatMessage"]{margin-left:0!important;margin-right:0!important}.jv-orb{width:56px;height:56px}}
</style>
"""

STATUS = {  # state -> (label, colour)
    "idle": ("Standing by", "#5ee6a8"),
    "listening": ("Jarvis is listening", "#ffd24a"),
    "transcribing": ("Transcribing your voice", "#ffd24a"),
    "thinking": ("Processing request", "#00e5ff"),
    "searching": ("Searching the web", "#7c9cff"),
    "imaging": ("Generating image", "#ff2bd6"),
    "reading": ("Reading file", "#7c9cff"),
    "responding": ("Typing response", "#00e5ff"),
    "speaking": ("Speaking", "#5ee6a8"),
    "error": ("Something went wrong", "#ff5a5a"),
}


def inject_theme(name="Cyberpunk Neon"):
    p = PALETTES.get(name, PALETTES["Cyberpunk Neon"])
    css = _CSS
    for k in sorted(p, key=len, reverse=True):      # longest first: '__accent2' before '__accent'
        css = css.replace(f"__{k}", p[k])
    st.markdown(css, unsafe_allow_html=True)


def status_html(state="idle", text=None):
    label, color = STATUS.get(state, STATUS["idle"])
    animated = state not in ("idle", "error")
    dots = '<span class="jv-dots"><span>.</span><span>.</span><span>.</span></span>' if animated else ""
    return f'<div class="jv-status" style="--c:{color}"><span class="dot"></span>{text or label}{dots}</div>'


def render_status(slot, state="idle", text=None):
    """slot is an st.empty() placeholder - call again later to update it."""
    slot.markdown(status_html(state, text), unsafe_allow_html=True)


def hud_cards(items):
    cards = "".join(f'<div class="jv-card"><small>{k}</small><div>{v}</div></div>' for k, v in items)
    st.markdown(f'<div class="jv-hud">{cards}</div>', unsafe_allow_html=True)


def typing_effect(slot, text, delay=0.008, chunk=3):
    """Types out locally-generated replies (LLM replies stream natively)."""
    shown = ""
    for i in range(0, len(text), chunk):
        shown = text[: i + chunk]
        slot.markdown(shown + " ▌")
        time.sleep(delay)
    slot.markdown(text)


def render_top_ticker(display_name, school, w, location=""):
    """Fixed, slowly scrolling bar: title + live weather + 3-day outlook."""
    parts = [f"<b>⚡ JARVIS AI CORE</b> // {school} // Welcome, {display_name}"]
    if w.get("ok"):
        parts.append(f"{w['icon']} <b>{w['temp']}°C</b> {w['desc']} in {w['city']}")
        parts.append(f"Feels {w['feels']}° · 💧 {w['humidity']}% · 💨 {w['wind']} km/h")
        parts += [f"{d['day']} {d['icon']} {d['hi']}°/{d['lo']}° · {d['rain']}% rain" for d in w["days"]]
    else:
        parts.append("🌐 Weather unavailable right now")
    if location:
        parts.append(f"📍 {location}")
    track = "".join(f"<span>{p}</span>" for p in parts)
    st.markdown(f'<div class="jv-ticker"><div class="jv-ticker-track">{track}{track}</div></div>', unsafe_allow_html=True)


def hide_sidebar():
    st.markdown("<style>[data-testid=\"stSidebar\"],[data-testid=\"stSidebarCollapsedControl\"],[data-testid=\"stExpandSidebarButton\"]{display:none!important}</style>",
                unsafe_allow_html=True)


_SCROLL_JS = """<script>(function(){const d=window.parent.document;
const el=d.querySelector('[data-testid="stMain"]')||d.querySelector('section.main')||d.querySelector('[data-testid="stAppViewContainer"]');
if(!el) return; let last=-1,idle=0,stop=false; const kill=()=>{stop=true};
['wheel','touchstart','keydown'].forEach(ev=>d.addEventListener(ev,kill,{once:true,passive:true}));
const iv=setInterval(()=>{ if(stop){clearInterval(iv);return;} const h=el.scrollHeight;
  el.scrollTo({top:h,behavior:'smooth'}); if(h===last) idle++; else {idle=0;last=h;} if(idle>__IDLE__) clearInterval(iv);},300);})();</script>"""


def auto_scroll(idle=40):
    """Keeps the page scrolled to the newest text while Jarvis types. Stops if you scroll yourself
    or when nothing has grown for `idle` ticks (~0.3s each)."""
    components.html(_SCROLL_JS.replace("__IDLE__", str(int(idle))), height=0)
