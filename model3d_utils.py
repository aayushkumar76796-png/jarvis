"""'Generate a 3D model of Iron Man Mark 85' - Jarvis designs the object from simple 3-D shapes (JSON scene, so no
generated code ever runs), and a three.js viewer shows it: drag to rotate, scroll / pinch to zoom."""
import json
import os
import re
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import study_utils as su
from data_paths import path as _dp
from html_safe import js

ROOT = _dp("models3d")
SHAPES = {"box": 3, "sphere": 1, "cylinder": 3, "cone": 2, "torus": 2}

_PROMPT = """You are a 3D modeller. Build the requested object ONLY from simple primitives and reply with ONLY JSON:
{"title": "short name", "parts": [{"shape": "box|sphere|cylinder|cone|torus", "size": [...], "pos": [x,y,z], "rot": [rx,ry,rz], "color": "#rrggbb", "metal": 0.0-1.0, "glow": false, "mirror": false}]}
Rules: object about 4 units tall, centred at the origin, y is up, z faces the viewer. rot is in DEGREES.
size: box=[width,height,depth]; sphere=[radius]; cylinder=[radiusTop,radiusBottom,height]; cone=[radius,height]; torus=[radius,tube].
"mirror": true duplicates the part on the other side (x -> -x) - use it for arms, legs, wings, wheels, eyes. Use 30-70 parts with real detail
(head, body, limbs, panels, lights, trim) and realistic colours. glow=true for lights / reactors / eyes."""


def _num(v, d=0.0, lo=-20, hi=20):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return d


def validate_scene(raw):
    """Clamps everything the model returned - only whitelisted shapes and numbers get through."""
    parts = []
    for p in (raw.get("parts") or [])[:90]:
        shape = p.get("shape")
        if shape not in SHAPES:
            continue
        size = [_num(x, 1, 0.01, 12) for x in (p.get("size") or [])][:SHAPES[shape]]
        size += [1.0] * (SHAPES[shape] - len(size))
        col = p.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p.get("color", ""))) else "#9aa7c7"
        parts.append({"shape": shape, "size": size, "pos": [_num(x) for x in (p.get("pos") or [0, 0, 0])][:3] + [0] * (3 - len((p.get("pos") or [0, 0, 0])[:3])),
                      "rot": [_num(x, 0, -360, 360) for x in (p.get("rot") or [0, 0, 0])][:3] + [0] * (3 - len((p.get("rot") or [0, 0, 0])[:3])),
                      "color": col, "metal": _num(p.get("metal", .3), .3, 0, 1), "glow": bool(p.get("glow")), "mirror": bool(p.get("mirror"))})
    if not parts:
        raise ValueError("the model returned no usable parts")
    return {"title": re.sub(r"[<>&\"']", "", str(raw.get("title", "3D model")))[:60], "parts": parts}


def generate_scene(client, model, prompt):
    r = client.chat.completions.create(model=model, temperature=0.5,
                                       messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": f"Build: {prompt}"}])
    txt = r.choices[0].message.content or ""
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("no JSON in the reply")
    return validate_scene(json.loads(m.group(0)))


# ----------------------------- storage -----------------------------
def _dir(user):
    p = os.path.join(ROOT, "".join(c for c in user if c.isalnum() or c in "_-") or "user")
    os.makedirs(p, exist_ok=True)
    return p


def save_scene(user, prompt, scene):
    name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:5]}.json"
    json.dump({"prompt": prompt, "created": datetime.now().isoformat(timespec="seconds"), "scene": scene},
              open(os.path.join(_dir(user), name), "w", encoding="utf-8"), indent=1)
    return name


def load_scene(user, name):
    if not name or os.path.basename(name) != name:
        return None
    try:
        return json.load(open(os.path.join(_dir(user), name), encoding="utf-8"))
    except Exception:
        return None


def list_scenes(user):
    out = []
    for f in sorted(os.listdir(_dir(user)), reverse=True):
        d = load_scene(user, f)
        if d:
            out.append({"file": f, **d})
    return out


def delete_scene(user, name):
    if os.path.basename(name) == name:
        try:
            os.remove(os.path.join(_dir(user), name))
        except OSError:
            pass


# ----------------------------- viewer -----------------------------
_VIEWER = """
<div id="w" style="width:100%;height:__H__px;border-radius:14px;overflow:hidden;background:radial-gradient(ellipse at center,#1a0f06,#030201);position:relative">
<div id="t" style="position:absolute;left:12px;top:8px;color:__ACC__;font:600 13px monospace;z-index:2">__TITLE__ · drag to rotate · scroll to zoom</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function(){
const S=__SCENE__,box=document.getElementById('w');
if(!window.THREE){box.innerHTML='<div style="color:#fff;padding:20px;font:14px sans-serif">3D viewer needs internet (three.js from cdnjs).</div>';return;}
const scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(45,box.clientWidth/box.clientHeight,.1,200);
const ren=new THREE.WebGLRenderer({antialias:true,alpha:true});ren.setSize(box.clientWidth,box.clientHeight);ren.setPixelRatio(Math.min(2,window.devicePixelRatio||1));box.appendChild(ren.domElement);
scene.add(new THREE.AmbientLight(0xffffff,.55));const d1=new THREE.DirectionalLight(0xffffff,.9);d1.position.set(4,6,5);scene.add(d1);
const d2=new THREE.DirectionalLight(0xffb070,.5);d2.position.set(-5,2,-4);scene.add(d2);scene.add(new THREE.PointLight(0xff9a1f,.6,30));
const g=new THREE.Group();scene.add(g);const rad=Math.PI/180;
function geo(p){const s=p.size;switch(p.shape){case'box':return new THREE.BoxGeometry(s[0],s[1],s[2]);case'sphere':return new THREE.SphereGeometry(s[0],24,18);
 case'cylinder':return new THREE.CylinderGeometry(s[0],s[1],s[2],24);case'cone':return new THREE.ConeGeometry(s[0],s[1],24);default:return new THREE.TorusGeometry(s[0],s[1],12,32);}}
function add(p,mir){const m=new THREE.Mesh(geo(p),new THREE.MeshStandardMaterial({color:p.color,metalness:p.metal,roughness:.55-p.metal*.35,emissive:p.glow?p.color:0x000000,emissiveIntensity:p.glow?.9:0}));
 m.position.set(mir?-p.pos[0]:p.pos[0],p.pos[1],p.pos[2]);m.rotation.set(p.rot[0]*rad,(mir?-1:1)*p.rot[1]*rad,(mir?-1:1)*p.rot[2]*rad);g.add(m);}
S.parts.forEach(p=>{add(p,false);if(p.mirror&&Math.abs(p.pos[0])>.001)add(p,true);});
const bb=new THREE.Box3().setFromObject(g),c=bb.getCenter(new THREE.Vector3()),sz=bb.getSize(new THREE.Vector3()),m=Math.max(sz.x,sz.y,sz.z)||4;
g.position.sub(c);let dist=m*2.1;cam.position.set(0,m*.1,dist);cam.lookAt(0,0,0);
const grid=new THREE.GridHelper(m*2.2,20,0xff9a1f,0x553311);grid.position.y=-sz.y/2-.02;scene.add(grid);
let rx=-.15,ry=0,drag=false,lx=0,ly=0,auto=true;
const el=ren.domElement;el.style.touchAction='none';
el.addEventListener('pointerdown',e=>{drag=true;auto=false;lx=e.clientX;ly=e.clientY;el.setPointerCapture(e.pointerId);});
el.addEventListener('pointermove',e=>{if(!drag)return;ry+=(e.clientX-lx)*.01;rx+=(e.clientY-ly)*.01;rx=Math.max(-1.4,Math.min(1.4,rx));lx=e.clientX;ly=e.clientY;});
el.addEventListener('pointerup',()=>{drag=false;setTimeout(()=>auto=true,2500);});
el.addEventListener('wheel',e=>{e.preventDefault();dist=Math.max(m*.8,Math.min(m*5,dist+e.deltaY*.01*m*.2));},{passive:false});
(function loop(){requestAnimationFrame(loop);if(auto)ry+=.006;g.rotation.set(rx,ry,0);cam.position.z=dist;ren.render(scene,cam);})();
})();
</script>"""


def render_viewer(scene, height=400, accent="#ff9a1f"):
    components.html(_VIEWER.replace("__SCENE__", js(scene)).replace("__H__", str(int(height))).replace("__ACC__", accent)
                    .replace("__TITLE__", re.sub(r"[<>\"']", "", scene.get("title", "3D model"))), height=int(height) + 6)


def render_models_page(user):
    items = list_scenes(user)
    st.caption(f"{len(items)} saved 3D model(s) · saved in `jarvis_data/models3d/` · create one in chat: *generate a 3D model of a robot dog*")
    if not items:
        st.info("No 3D models yet. Try `/3d Iron Man Mark 85` in chat.")
    for it in items:
        with st.expander(f"🧊 {it['scene'].get('title', 'model')} · {it['created'][:16].replace('T', ' ')} · {len(it['scene']['parts'])} parts"):
            st.caption(f"Prompt: {it['prompt']}")
            render_viewer(it["scene"], 360)
            a, b = st.columns(2)
            a.download_button("⬇️ Scene (.json)", json.dumps(it["scene"], indent=1).encode(), it["file"], "application/json", key=f"m3d_dl_{it['file']}",
                              use_container_width=True)
            if b.button("🗑 Delete", key=f"m3d_del_{it['file']}", use_container_width=True):
                delete_scene(user, it["file"])
                st.rerun()
