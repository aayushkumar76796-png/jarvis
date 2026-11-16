"""Orb hero + one-click command chips."""
import streamlit as st
import streamlit.components.v1 as components

from html_safe import js

# (label, id, permission needed)
CHIPS = [  # (label, id, permission, local_only)
    ("📋 Summarize text", "clipboard", "chat", False),
    ("🎨 Make image", "image", "image", False),
    ("🧊 3D model", "model3d", "image", False),
    ("🕒 Schedule", "schedule", "tasks", False),
    ("✉️ Draft email", "email", "chat", False),
    ("📰 News", "news", "web", False),
    ("🧠 Quiz me", "quiz", "chat", False),
    ("🗞️ Daily brief", "brief", "chat", False),
    ("📅 What to study", "next", "study", False),
    ("🖥️ Analyze screen", "screen", "system", True),
]

ORB_TEXT = {"idle": "ONLINE", "listening": "LISTENING", "transcribing": "TRANSCRIBING", "thinking": "PROCESSING", "searching": "SEARCHING",
            "reading": "READING", "imaging": "RENDERING", "responding": "RESPONDING", "speaking": "SPEAKING", "error": "FAULT"}

ORB_COLORS = {"Gold": {"core": "#fff3d1", "a": "#ffb23f", "b": "#ff6a1a"}, "Cyan": {"core": "#e6fbff", "a": "#2de2ff", "b": "#2b7bff"},
              "Magenta": {"core": "#ffe6fb", "a": "#ff5fd6", "b": "#8a3dff"}}

ORB_STYLES = ["Particle Sphere", "Arc Reactor", "Voice Wave"]

# Three HUD styles on one canvas. When ElevenLabs audio is playing, the orb reacts to the REAL voice (parent.__jvAnalyser).
_HUD_HTML = """
<div style="position:relative;width:100%;height:__H__px;background:radial-gradient(ellipse at center,#120a04 0%,#030201 78%);border-radius:14px;overflow:hidden">
<canvas id="c" style="width:100%;height:100%;display:block"></canvas></div>
<script>
(function(){
const C=__COL__,STYLE=__STYLE__,STATE=__STATE__,NAME=__NAME__,LABEL=__LABEL__,INFO=__INFO__;
const cv=document.getElementById('c'),ctx=cv.getContext('2d');let W,H,D=window.devicePixelRatio||1;
function fit(){const r=cv.getBoundingClientRect();W=r.width;H=r.height;cv.width=W*D;cv.height=H*D;ctx.setTransform(D,0,0,D,0,0);}fit();window.addEventListener('resize',fit);
function rgb(h){h=h.replace('#','');return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];}
const cA=rgb(C.a),cB=rgb(C.b),cC=rgb(C.core);const col=(c,a)=>'rgba('+c[0]+','+c[1]+','+c[2]+','+a+')';
const spd={idle:.45,listening:.9,transcribing:1.1,thinking:2.4,searching:1.7,reading:1.3,imaging:2,responding:1.2,speaking:1.3,error:.2}[STATE]||.5;
const ampB={idle:.04,listening:.16,transcribing:.14,thinking:.1,searching:.12,reading:.1,imaging:.18,responding:.2,speaking:.3,error:.02}[STATE]||.06;
const swirl={idle:.5,listening:.8,transcribing:.9,thinking:2.2,searching:1.4,reading:1.0,imaging:1.6,responding:1.0,speaking:.9,error:.2}[STATE]||.5;
const PW=window.parent,fd=new Uint8Array(64);let lvl=0;
function audioLevel(){try{const an=PW.__jvAnalyser;if(an){an.getByteFrequencyData(fd);let s=0;for(let i=2;i<30;i++)s+=fd[i];return s/28/255;}}catch(e){}return -1;}
const N=W<520?1000:1700,P=[];
for(let i=0;i<N;i++){const y=1-2*(i+.5)/N,r=Math.sqrt(1-y*y),th=i*2.399963;P.push({x:Math.cos(th)*r,y:y,z:Math.sin(th)*r,ph:Math.random()*6.283,sp:.5+Math.random(),sz:Math.random()});}
const step=Math.max(1,Math.floor(N/420)),sub=[];for(let i=0;i<N;i+=step)sub.push(i);
const links=[];sub.forEach(a=>{let best=[];sub.forEach(b=>{if(a===b)return;const d=(P[a].x-P[b].x)**2+(P[a].y-P[b].y)**2+(P[a].z-P[b].z)**2;best.push([d,b]);});best.sort((p,q)=>p[0]-q[0]);links.push([a,best[0][1]],[a,best[1][1]]);});
const rings=[];for(let k=0;k<7;k++)rings.push({tilt:Math.random()*3,rad:1.05+k*.07,sp:(.4+Math.random()*.9)*(k%2?-1:1),n:110,ph:Math.random()*6.28});
let t=0;const pos=new Array(N);
function sphere(cx,cy,R,amp){
 const yaw=t*.55,pitch=.5+Math.sin(t*.35)*.1,cy_=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
 function proj(x,y,z){const x1=x*cy_+z*sy,z1=-x*sy+z*cy_,y1=y*cp-z1*sp,z2=y*sp+z1*cp,f=1/(1-z2*.32);return [cx+x1*R*f,cy+y1*R*f,z2,f];}
 ctx.globalCompositeOperation='lighter';
 const pulse=1+Math.sin(t*4)*.05*(1+amp*4);const g=ctx.createRadialGradient(cx,cy,0,cx,cy,R*.85*pulse);g.addColorStop(0,col(cC,.75));g.addColorStop(.25,col(cA,.42));g.addColorStop(.7,col(cB,.1));g.addColorStop(1,'rgba(0,0,0,0)');
 ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*.9,0,7);ctx.fill();
 for(let i=0;i<N;i++){const p=P[i];const tw=swirl*(p.y*1.6+Math.sin(t*.7)*.8);const c=Math.cos(tw),s=Math.sin(tw);
  const n=Math.sin(t*3*p.sp+p.ph)*(.5+.5*Math.sin(t*1.7+i*.013)),rad=1+amp*n+(i%7===0?amp*.8*Math.sin(t*5+p.ph):0)-(STATE==='thinking'?.12*(.5+.5*Math.sin(t*2)):0);
  const q=proj((p.x*c-p.z*s)*rad,p.y*rad,(p.x*s+p.z*c)*rad);pos[i]=q;const dep=(q[2]+1)/2,a=.18+.8*dep;
  ctx.fillStyle=dep>.78?col(cC,a):col(dep>.4?cA:cB,a);const sz=(.6+p.sz*1.5)*q[3];ctx.fillRect(q[0],q[1],sz,sz);}
 ctx.lineWidth=.6;links.forEach(l=>{const a=pos[l[0]],b=pos[l[1]];if(!a||!b)return;const dep=(a[2]+b[2])/4+.5;ctx.strokeStyle=col(cA,.05+.2*dep);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();});
 rings.forEach(r=>{ctx.beginPath();for(let k=0;k<=r.n;k++){const th=k/r.n*6.283+t*r.sp+r.ph,x=Math.cos(th)*r.rad,z=Math.sin(th)*r.rad;
   const q=proj(x,z*Math.sin(r.tilt)*.6,z*Math.cos(r.tilt));k?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]);}
   ctx.strokeStyle=col(cA,.16);ctx.lineWidth=.8;ctx.stroke();
   const th=t*r.sp*1.7+r.ph,q=proj(Math.cos(th)*r.rad,Math.sin(th)*r.rad*Math.sin(r.tilt)*.6,Math.sin(th)*r.rad*Math.cos(r.tilt));ctx.fillStyle=col(cC,.9);ctx.beginPath();ctx.arc(q[0],q[1],2*q[3],0,7);ctx.fill();});
 ctx.globalCompositeOperation='source-over';}
function arc(r,a0,a1,w,c,dash){ctx.beginPath();ctx.setLineDash(dash||[]);ctx.lineWidth=w;ctx.strokeStyle=c;ctx.arc(0,0,r,a0,a1);ctx.stroke();ctx.setLineDash([]);}
const bars=96,bl=new Array(bars).fill(0);
function reactor(cx,cy,R,amp){ctx.save();ctx.translate(cx,cy);ctx.globalCompositeOperation='lighter';
 const g=ctx.createRadialGradient(0,0,R*.1,0,0,R*1.5);g.addColorStop(0,col(cA,.35));g.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=g;ctx.beginPath();ctx.arc(0,0,R*1.5,0,7);ctx.fill();
 ctx.save();ctx.rotate(t*.6);arc(R*1.12,0,6.2,2,col(cA,.8),[18,10]);ctx.restore();ctx.save();ctx.rotate(-t*.9);arc(R*1.03,0,4.2,3,col(cB,.85),[60,22]);ctx.restore();
 ctx.save();ctx.rotate(t*1.4);arc(R*.82,.3,2.4,4,col(cA,.9));arc(R*.82,3.4,5.4,4,col(cA,.5));ctx.restore();
 for(let i=0;i<72;i++){ctx.save();ctx.rotate(i*Math.PI/36+t*.2);ctx.fillStyle=i%6?col(cA,.4):col(cA,1);ctx.fillRect(R*1.2,-1,i%6?6:12,2);ctx.restore();}
 for(let i=0;i<bars;i++){const tg=amp*(.35+.65*Math.abs(Math.sin(t*3+i*.5)*Math.cos(t*2.1+i*.13)))+Math.random()*amp*.3;bl[i]+=(tg-bl[i])*.3;ctx.save();ctx.rotate(i*Math.PI*2/bars);ctx.fillStyle=i%2?col(cA,1):col(cB,1);ctx.fillRect(R*.62,-1.2,3+bl[i]*R*.55,2.4);ctx.restore();}
 const pulse=1+Math.sin(t*4)*.06*(1+spd);ctx.save();ctx.scale(pulse,pulse);const c=ctx.createRadialGradient(0,0,0,0,0,R*.5);c.addColorStop(0,'#fff');c.addColorStop(.25,col(cA,1));c.addColorStop(1,col(cB,.15));
 ctx.fillStyle=c;ctx.beginPath();ctx.arc(0,0,R*.34,0,7);ctx.fill();ctx.strokeStyle='rgba(255,255,255,.6)';ctx.lineWidth=1.5;
 for(let i=0;i<3;i++){ctx.save();ctx.rotate(i*Math.PI*2/3+t);ctx.beginPath();ctx.moveTo(0,-R*.12);ctx.lineTo(R*.3,R*.08);ctx.lineTo(-R*.3,R*.08);ctx.closePath();ctx.stroke();ctx.restore();}ctx.restore();
 ctx.save();ctx.rotate(t*1.2);const sw=ctx.createLinearGradient(0,0,R,0);sw.addColorStop(0,col(cA,0));sw.addColorStop(1,col(cA,.4));ctx.fillStyle=sw;ctx.beginPath();ctx.moveTo(0,0);ctx.arc(0,0,R*.9,-.25,0);ctx.fill();ctx.restore();
 ctx.restore();}
function wave(cx,cy,R,amp){ctx.globalCompositeOperation='lighter';
 const g=ctx.createRadialGradient(cx,cy,0,cx,cy,R*.6);g.addColorStop(0,col(cC,.8));g.addColorStop(.4,col(cA,.35));g.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*.6*(1+amp*.5),0,7);ctx.fill();
 for(let i=0;i<bars;i++){const tg=amp*(.3+.7*Math.abs(Math.sin(t*3+i*.5)*Math.cos(t*1.9+i*.17)))+Math.random()*amp*.25;bl[i]+=(tg-bl[i])*.3;ctx.save();ctx.translate(cx,cy);ctx.rotate(i*Math.PI*2/bars);ctx.fillStyle=i%2?col(cA,.95):col(cB,.95);ctx.fillRect(R*.42,-1.3,3+bl[i]*R*.5,2.6);ctx.restore();}
 const x0=W*.05,x1=W*.95;for(let k=0;k<5;k++){ctx.beginPath();for(let x=x0;x<=x1;x+=4){const u=(x-x0)/(x1-x0),env=Math.pow(Math.sin(Math.PI*u),2);
   const y=cy+Math.sin(u*(7+k*2.3)+t*(1.4+k*.5)+k)*(8+amp*H*.32)*env*(1-k*.12);x===x0?ctx.moveTo(x,y):ctx.lineTo(x,y);}
   ctx.strokeStyle=col(k%2?cB:cA,.75-k*.1);ctx.lineWidth=2-k*.25;ctx.stroke();}
 ctx.globalCompositeOperation='source-over';}
function frame(){t+=.016*spd;ctx.clearRect(0,0,W,H);
 const lv=audioLevel();lvl=lv>=0?lvl+(lv-lvl)*.35:lvl*.9;const amp=lv>=0?Math.max(ampB*.4,lvl*1.15):ampB;
 const cx=W/2,cy=H/2+4,R=Math.min(W*.45,H*.42);
 ctx.save();ctx.globalAlpha=.06;ctx.strokeStyle=col(cA,1);ctx.lineWidth=1;for(let y=(t*30)%6;y<H;y+=6){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}ctx.restore();
 if(STYLE==='Arc Reactor')reactor(cx,cy,R,amp);else if(STYLE==='Voice Wave')wave(cx,cy,R,amp);else sphere(cx,cy,R,amp);
 ctx.strokeStyle=col(cA,.75);ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(W*.08,16);ctx.lineTo(W*.58,16);ctx.stroke();ctx.fillStyle=col(cA,.9);ctx.fillRect(W*.58,13,W*.05,6);
 ctx.strokeStyle=col(cA,.35);ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(W*.08,22);ctx.lineTo(W*.34,22);ctx.stroke();
 ctx.strokeStyle=col(cA,.6);ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(14,H*.16);ctx.lineTo(14,H*.52);ctx.stroke();ctx.fillStyle=col(cA,.8);ctx.fillRect(11,H*.52,6,H*.04);
 ctx.beginPath();ctx.moveTo(W*.08,H-16);ctx.lineTo(W*.82,H-16);ctx.stroke();
 ctx.save();ctx.translate(W-24,H-24);ctx.rotate(t*.8);ctx.strokeStyle=col(cA,.9);ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(0,0,8,0,7);ctx.stroke();for(let k=0;k<6;k++){ctx.rotate(1.047);ctx.beginPath();ctx.moveTo(8,0);ctx.lineTo(12,0);ctx.stroke();}ctx.restore();
 ctx.textAlign='left';ctx.fillStyle=col(cA,.95);ctx.font='600 '+Math.max(11,W/64)+'px monospace';ctx.fillText('● '+LABEL+(lv>=0?'  ♪':''),W*.08,40);
 ctx.textAlign='center';ctx.font='600 '+Math.max(13,W/46)+'px "Chakra Petch",monospace';ctx.fillText('J . A . R . V . I . S',cx,H-26);
 ctx.font='500 '+Math.max(9,W/90)+'px monospace';ctx.fillStyle=col(cA,.6);ctx.fillText('AT YOUR SERVICE, '+NAME.toUpperCase(),cx,H-6);
 if(W>600){ctx.font='11px monospace';INFO.slice(0,4).forEach((p,i)=>{ctx.textAlign='left';ctx.fillStyle=col(cA,.7);ctx.fillText(p[0],W*.045,H*.62+i*34);ctx.fillStyle='#fff1de';ctx.fillText(p[1],W*.045,H*.62+14+i*34);});
  INFO.slice(4,8).forEach((p,i)=>{ctx.textAlign='right';ctx.fillStyle=col(cA,.7);ctx.fillText(p[0],W*.955,38+i*34);ctx.fillStyle='#fff1de';ctx.fillText(p[1],W*.955,52+i*34);});}
 else if(INFO.length){ctx.textAlign='center';ctx.font='10px monospace';ctx.fillStyle='rgba(255,241,222,.75)';ctx.fillText(INFO.slice(0,3).map(p=>p[1]).join('  ·  '),cx,H-44);}
 requestAnimationFrame(frame);}
frame();})();
</script>"""


def render_orb(slot, display_name, state="idle", info=None):
    """Realtime Orb 'video interface'. `slot` = st.empty(); call again with a new state to change the animation.
    `info` = {label: value} telemetry shown on wide screens. Style/colour come from Control Panel -> Look."""
    import json as _json
    from settings_utils import get_settings
    from theme_utils import PALETTES
    s = get_settings()
    if s.get("orb_color", "Gold") == "Theme":
        p = PALETTES.get(s.get("theme", "Stark Gold"), PALETTES["Stark Gold"])
        col = {"core": "#ffffff", "a": p["accent"], "b": p["accent2"]}
    else:
        col = ORB_COLORS.get(s.get("orb_color", "Gold"), ORB_COLORS["Gold"])
    style = s.get("orb_style", "Particle Sphere")
    pairs = [[str(k).upper(), str(v)] for k, v in (info or {}).items()]
    html = (_HUD_HTML.replace("__H__", "380").replace("__COL__", js(col)).replace("__STATE__", js(state))
            .replace("__STYLE__", js(style if style in ORB_STYLES else ORB_STYLES[0]))
            .replace("__LABEL__", js(ORB_TEXT.get(state, "ONLINE"))).replace("__NAME__", js(display_name))
            .replace("__INFO__", js(pairs)))
    with slot.container():
        components.html(html, height=384)


def render_command_chips(can, local=False):
    """Returns the clicked chip id (or None). `can(perm)` filters chips by role."""
    clicked = None
    visible = [c for c in CHIPS if can(c[2]) and (local or not c[3])]
    with st.container(key="chips"):
        for r in range(0, len(visible), 5):
            row = visible[r: r + 5]
            cols = st.columns(len(row))
            for col, (label, cid, _, _l) in zip(cols, row):
                if col.button(label, key=f"chip_{cid}", use_container_width=True):
                    clicked = cid
    return clicked
