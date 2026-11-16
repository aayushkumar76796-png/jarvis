"""Voice in/out: configurable TTS (browser or offline), Groq Whisper STT, wake word."""
import base64
import json
import os
import re
import threading
import urllib.error
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

from html_safe import js


def clean_for_speech(text, limit=700):
    text = re.sub(r"```.*?```", " code block omitted. ", text or "", flags=re.S)
    text = re.sub(r"https?://\S+", " link ", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


_VOICE_JS = """
<script>
(function(){
  const text=%(text)s, cfg=%(cfg)s, P=window.parent;
  if(!('speechSynthesis' in P)) return;
  const pickVoice=()=>{
    const vs=P.speechSynthesis.getVoices(); if(!vs.length) return null;
    if(cfg.name){const v=vs.find(v=>v.name.toLowerCase().includes(cfg.name.toLowerCase())); if(v) return v;}
    const rules={Female:/female|zira|samantha|aria|jenny|heera|google uk english female/i,
                 Male:/(^|\\W)male|david|daniel|guy|mark|ravi|google uk english male/i};
    if(cfg.pref==='British') return vs.find(v=>v.lang==='en-GB')||null;
    if(cfg.pref==='Indian English') return vs.find(v=>v.lang==='en-IN')||null;
    if(rules[cfg.pref]) return vs.find(v=>rules[cfg.pref].test(v.name)&&v.lang.startsWith('en'))||null;
    return null;
  };
  const go=()=>{
    P.speechSynthesis.cancel();
    const u=new P.SpeechSynthesisUtterance(text);
    u.rate=cfg.rate;u.pitch=cfg.pitch;u.volume=cfg.volume;
    const v=pickVoice(); if(v){u.voice=v;u.lang=v.lang;}
    P.speechSynthesis.speak(u);
  };
  if(P.speechSynthesis.getVoices().length) go(); else P.speechSynthesis.onvoiceschanged=go;
  if(cfg.notify && 'Notification' in P && P.Notification.permission==='granted'){
    try{new P.Notification(%(title)s,{body:text.slice(0,140)});}catch(e){}
  }
})();
</script>
"""


ELEVEN_API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"      # "Rachel" - change it in Control Panel -> Voice


def eleven_ready():
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


@st.cache_data(ttl=3600, max_entries=60, show_spinner=False)
def _eleven_tts(text, voice, model, stability, similarity, speed):
    """ElevenLabs text-to-speech -> mp3 bytes. Cached per text/voice so repeated lines cost no credits."""
    body = json.dumps({"text": text, "model_id": model,
                       "voice_settings": {"stability": stability, "similarity_boost": similarity,
                                          "speed": max(0.7, min(1.2, speed))}}).encode()
    req = urllib.request.Request(f"{ELEVEN_API}/text-to-speech/{voice}?output_format=mp3_44100_64", data=body, method="POST",
                                 headers={"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", ""), "Content-Type": "application/json",
                                          "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def eleven_voices():
    """[(name, voice_id)] for the voices on your ElevenLabs account."""
    req = urllib.request.Request(f"{ELEVEN_API}/voices", headers={"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "")})
    with urllib.request.urlopen(req, timeout=15) as r:
        return [(v["name"], v["voice_id"]) for v in json.loads(r.read())["voices"]]


_AUDIO_JS = """<script>(function(){
const P=window.parent,src="data:audio/mpeg;base64,__B64__",vol=__VOL__;
function banner(a){try{const d=P.document;let b=d.getElementById('jv-hear');if(b)b.remove();b=d.createElement('button');b.id='jv-hear';b.textContent='🔊 Tap to hear Jarvis';
 b.style.cssText='position:fixed;left:50%;bottom:96px;transform:translateX(-50%);z-index:99999;padding:14px 26px;border-radius:999px;border:0;background:linear-gradient(90deg,#ff9a1f,#ff5a1a);color:#120800;font:600 16px sans-serif;box-shadow:0 8px 30px rgba(255,140,30,.6)';
 b.onclick=()=>{a.play();b.remove();};d.body.appendChild(b);setTimeout(()=>{try{b.remove()}catch(e){}},25000);}catch(e){}}
try{ if(P.__jvAudio){try{P.__jvAudio.pause();}catch(e){}}
 const a=new P.Audio(src);a.volume=vol;P.__jvAudio=a;a.onended=()=>{P.__jvAnalyser=null;};
 const AC=P.AudioContext||P.webkitAudioContext;const ctx=P.__jvCtx||(P.__jvCtx=new AC());
 const go=()=>{ if(ctx.state==='running'){try{const n=ctx.createMediaElementSource(a),an=ctx.createAnalyser();an.fftSize=128;n.connect(an);an.connect(ctx.destination);P.__jvAnalyser=an;}catch(e){}}
   a.play().catch(()=>banner(a)); };
 (ctx.state==='suspended'?ctx.resume():Promise.resolve()).then(go).catch(go);
}catch(e){}})();</script>"""


def _http_error_text(e):
    """Turns an ElevenLabs HTTP error into a plain-English hint."""
    try:
        body = json.loads(e.read().decode("utf-8", "ignore"))
        detail = body.get("detail", body)
        msg = detail.get("message") if isinstance(detail, dict) else str(detail)
    except Exception:
        msg = ""
    hint = {401: "API key is wrong or lacks the Text-to-Speech permission (make a new key with all permissions)",
            404: "that voice ID does not exist on your account - copy it again from elevenlabs.io → Voices → ID",
            402: "your plan does not include this voice through the API (free plans: use premade voices or voices you created)",
            403: "your plan/key is not allowed to use this voice via the API",
            422: "invalid request (check model / voice ID)", 429: "too many requests or no credits left"}.get(e.code, "")
    return f"HTTP {e.code}: {msg or hint}" + (f" → {hint}" if msg and hint else "")


def eleven_test(s):
    """-> (ok, message, mp3_bytes|None) for the Control Panel 'Test' button."""
    if not eleven_ready():
        return False, "ELEVENLABS_API_KEY not found - put it in .env (then press Reload) or API Keys tab.", None
    voice = s.get("eleven_voice_id") or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    try:
        _eleven_tts.clear()
        data = _eleven_tts("Systems online. Voice link established.", voice, s.get("eleven_model", "eleven_flash_v2_5"),
                           float(s.get("eleven_stability", 0.5)), float(s.get("eleven_similarity", 0.75)), 1.0)
        return True, f"ElevenLabs works ✅ (voice {voice[:6]}…, {len(data) // 1024} KB audio)", data
    except urllib.error.HTTPError as e:
        return False, _http_error_text(e), None
    except Exception as e:
        return False, f"Could not reach ElevenLabs: {e}", None


def effective_engine(s):
    e = s.get("tts_engine", "Auto")
    return ("ElevenLabs" if eleven_ready() else "Browser") if e.startswith("Auto") else e.split(" ")[0]


def _speak_eleven(text, s):
    voice = s.get("eleven_voice_id") or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    data = _eleven_tts(text[: int(s.get("eleven_max_chars", 450))], voice, s.get("eleven_model", "eleven_flash_v2_5"),
                       float(s.get("eleven_stability", 0.5)), float(s.get("eleven_similarity", 0.75)), float(s.get("tts_rate", 1.0)))
    components.html(_AUDIO_JS.replace("__B64__", base64.b64encode(data).decode()).replace("__VOL__", str(float(s.get("tts_volume", 1.0)))), height=0)


def _speak_offline(text, s):
    """Server-side TTS through pyttsx3 (works when Jarvis runs on your own PC)."""
    try:
        import pyttsx3
    except ImportError:
        return False

    def run():
        try:
            eng = pyttsx3.init()
            eng.setProperty("rate", int(175 * float(s.get("tts_rate", 1.0))))
            eng.setProperty("volume", float(s.get("tts_volume", 1.0)))
            pref = s.get("tts_voice_pref", "Auto")
            if pref in ("Female", "Male"):
                for v in eng.getProperty("voices"):
                    hit = any(k in v.name.lower() for k in (("zira", "female", "samantha", "hazel") if pref == "Female"
                                                            else ("david", "male", "daniel", "mark")))
                    if hit:
                        eng.setProperty("voice", v.id)
                        break
            eng.say(text)
            eng.runAndWait()
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()
    return True


def speak_and_notify(text, title="Jarvis Notification", force=False):
    """Toast + spoken output using the voice settings from the sidebar."""
    st.toast((text or "")[:220], icon="🤖")
    s = st.session_state.get("settings", {})
    engine = s.get("tts_engine", "Auto (ElevenLabs if key found)")
    if engine.startswith("Auto"):
        engine = "ElevenLabs (realistic)" if eleven_ready() else "Browser (online)"
    if engine == "Off" or not (s.get("tts_enabled", True) or force):
        return
    spoken = clean_for_speech(text)
    if not spoken:
        return
    if engine.startswith("ElevenLabs"):
        if not eleven_ready():
            st.toast("ElevenLabs key missing - add ELEVENLABS_API_KEY in .env (using browser voice for now)", icon="🔑")
        else:
            try:
                _speak_eleven(spoken, s)
                return
            except urllib.error.HTTPError as e:
                st.toast(f"ElevenLabs {_http_error_text(e)[:90]} - using browser voice", icon="⚠️")
            except Exception as e:
                st.toast(f"ElevenLabs error ({str(e)[:60]}) - using browser voice", icon="⚠️")
    if engine.startswith("Offline") and _speak_offline(spoken, s):
        return
    cfg = {"rate": s.get("tts_rate", 1.0), "pitch": s.get("tts_pitch", 1.0), "volume": s.get("tts_volume", 1.0),
           "pref": s.get("tts_voice_pref", "Auto"), "name": s.get("tts_voice_name", ""), "notify": True}
    components.html(_VOICE_JS % {"text": js(spoken), "cfg": js(cfg), "title": js(title)}, height=0)


def transcribe_audio(client, audio_bytes, model="whisper-large-v3", language=None):
    """Groq Whisper. Sends bytes straight from memory - no temp files."""
    kwargs = {"model": model, "file": ("speech.wav", audio_bytes)}
    if language:
        kwargs["language"] = language
    return client.audio.transcriptions.create(**kwargs).text


def render_notification_permission_button():
    # Browsers only allow the permission prompt from a real click, so this is a real button.
    components.html("""
    <button id="b" style="padding:.45rem 1rem;border-radius:10px;border:1px solid #00e5ff55;background:#120a24;color:#e8f4ff;cursor:pointer;font:14px sans-serif">
      🔔 Enable desktop notifications</button>
    <script>
    const b=document.getElementById('b');
    if(!('Notification' in window)){b.textContent='Notifications not supported in this browser';b.disabled=true;}
    else if(Notification.permission==='granted'){b.textContent='🔔 Notifications enabled';}
    b.onclick=()=>Notification.requestPermission().then(p=>{b.textContent=p==='granted'?'🔔 Notifications enabled':'🔕 Notifications blocked';});
    </script>""", height=46)


def render_wake_word(enabled, phrase="hey jarvis", lang="en-IN"):
    """Hands-free trigger using the browser's SpeechRecognition (Chrome/Edge).

    Say '<wake phrase> <command>' and the command is submitted to the chat box.
    If you only say the phrase, the next sentence is used as the command.
    """
    if not enabled:
        return
    components.html("""
    <div id="s" style="font:13px sans-serif;color:#8a93b8;padding:2px 0">👂 starting wake word...</div>
    <script>
    (function(){
      const PHRASE=%(phrase)s.toLowerCase(), LANG=%(lang)s;
      const SR=window.SpeechRecognition||window.webkitSpeechRecognition, s=document.getElementById('s');
      if(!SR){s.textContent='Wake word needs Chrome or Edge.';return;}
      const doc=window.parent.document; let armed=false;
      function submit(text){
        const ta=doc.querySelector('[data-testid="stChatInputTextArea"]')||doc.querySelector('[data-testid="stChatInput"] textarea');
        if(!ta) return;
        const setter=Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype,'value').set;
        setter.call(ta,text); ta.dispatchEvent(new Event('input',{bubbles:true}));
        setTimeout(()=>{const b=doc.querySelector('[data-testid="stChatInputSubmitButton"]');
          if(b) b.click(); else ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));},180);
      }
      const r=new SR(); r.continuous=true; r.interimResults=false; r.lang=LANG;
      r.onresult=e=>{
        if(window.speechSynthesis&&speechSynthesis.speaking) return;   // don't hear Jarvis himself
        const t=e.results[e.results.length-1][0].transcript.trim(), low=t.toLowerCase();
        if(armed){armed=false;s.textContent='👂 listening for "'+PHRASE+'"';submit(t);return;}
        const i=low.indexOf(PHRASE);
        if(i<0) return;
        const cmd=t.slice(i+PHRASE.length).replace(/^[ ,.:;-]+/,'');
        if(cmd.length>2) submit(cmd); else {armed=true;s.textContent='🎙️ yes? say your command...';}
      };
      r.onend=()=>{try{r.start();}catch(e){}};
      r.onerror=ev=>{s.textContent='Wake word error: '+ev.error;};
      try{r.start();s.textContent='👂 listening for "'+PHRASE+'"';}catch(e){}
    })();
    </script>""" % {"phrase": js(phrase), "lang": js(lang)}, height=30)


_CLAP_JS = """
<div id="s" style="font:13px sans-serif;color:#b89570;padding:2px 0">👏 starting clap detector…</div>
<script>
(async function(){
 const CMD=__CMD__,SENS=__SENS__,s=document.getElementById('s'),P=window.parent,doc=P.document;
 function submit(text){const ta=doc.querySelector('[data-testid="stChatInputTextArea"]')||doc.querySelector('[data-testid="stChatInput"] textarea');if(!ta)return;
  const setter=Object.getOwnPropertyDescriptor(P.HTMLTextAreaElement.prototype,'value').set;setter.call(ta,text);ta.dispatchEvent(new Event('input',{bubbles:true}));
  setTimeout(()=>{const b=doc.querySelector('[data-testid="stChatInputSubmitButton"]');if(b)b.click();else ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));},180);}
 try{
  const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
  const AC=window.AudioContext||window.webkitAudioContext,ctx=new AC(),src=ctx.createMediaStreamSource(stream),an=ctx.createAnalyser();an.fftSize=1024;src.connect(an);
  const buf=new Float32Array(an.fftSize),thr=Math.max(.12,.95-SENS*.085);let prev=0,t1=0,cool=0;
  s.textContent='👏👏 double-clap detector ON';
  setInterval(()=>{an.getFloatTimeDomainData(buf);let peak=0,sum=0;for(let i=0;i<buf.length;i++){const v=buf[i],a=Math.abs(v);if(a>peak)peak=a;sum+=v*v;}
   const rms=Math.sqrt(sum/buf.length)||1e-6,now=performance.now();
   const talking=(P.speechSynthesis&&P.speechSynthesis.speaking)||(P.__jvAudio&&!P.__jvAudio.paused&&!P.__jvAudio.ended);
   const onset=peak>thr&&peak/rms>3.2&&prev<thr*.6;prev=peak;
   if(talking||now<cool)return;
   if(onset){if(t1&&now-t1>150&&now-t1<1300){t1=0;cool=now+3500;s.textContent='👏👏 detected!';submit(CMD);setTimeout(()=>{s.textContent='👏👏 double-clap detector ON';},2500);}else t1=now;}
   if(t1&&now-t1>1300)t1=0;},25);
 }catch(e){s.textContent='Clap detector needs microphone permission ('+e.name+')';}
})();
</script>"""


def render_clap_trigger(enabled, command="hello jarvis, wake up", sensitivity=6):
    """Double-clap -> sends `command` to Jarvis (like the 'turn on the lights' demo). Needs microphone permission."""
    if enabled:
        components.html(_CLAP_JS.replace("__CMD__", js(command)).replace("__SENS__", str(int(sensitivity))), height=30)
