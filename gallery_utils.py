"""Permanent image gallery: every generated picture is saved to disk (per user) with its prompt,
stamped with a small "JARVIS AI" tag, and can be re-opened from chats and the Gallery page."""
import io
import json
import os
import uuid
from datetime import datetime

import streamlit as st

from data_paths import path as _dp

ROOT = _dp("gallery")


def _dir(user):
    safe = "".join(c for c in user if c.isalnum() or c in "_-") or "user"
    path = os.path.join(ROOT, safe)
    os.makedirs(path, exist_ok=True)
    return path


def _index(user):
    p = os.path.join(_dir(user), "index.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return []


def _write_index(user, items):
    json.dump(items, open(os.path.join(_dir(user), "index.json"), "w", encoding="utf-8"), indent=1)


def brand(data, text="JARVIS AI"):
    """Stamps a small translucent tag in the bottom-right corner. Returns PNG bytes (raw bytes if Pillow is missing)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        w, h = img.size
        size = max(16, w // 38)
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        l, t, r, b = d.textbbox((0, 0), text, font=font)
        pad = size // 2
        x1, y1 = w - (r - l) - pad * 3, h - (b - t) - pad * 3
        d.rounded_rectangle((x1 - pad, y1 - pad // 2, w - pad, h - pad), radius=pad, fill=(8, 10, 24, 170),
                            outline=(0, 229, 255, 200), width=max(1, size // 14))
        d.text((x1, y1 - t), text, font=font, fill=(0, 229, 255, 235))
        out = io.BytesIO()
        Image.alpha_composite(img, layer).convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return data


def save_image(user, data, prompt="", enhanced="", style="", session_id="", stamp=True):
    """Saves to disk + index. Returns (filename, bytes_saved)."""
    data = brand(data) if stamp else data
    ext = "png" if data[:4] == b"\x89PNG" else "jpg"
    name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:5]}.{ext}"
    with open(os.path.join(_dir(user), name), "wb") as f:
        f.write(data)
    items = _index(user)
    items.insert(0, {"file": name, "prompt": prompt, "enhanced": enhanced, "style": style, "session": session_id,
                     "created": datetime.now().isoformat(timespec="seconds")})
    _write_index(user, items)
    return name, data


def load_image(user, filename):
    if not filename or os.path.basename(filename) != filename:   # block path tricks
        return None
    p = os.path.join(_dir(user), filename)
    return open(p, "rb").read() if os.path.exists(p) else None


def list_images(user, query=""):
    items = [i for i in _index(user) if os.path.exists(os.path.join(_dir(user), i["file"]))]
    q = query.lower().strip()
    return [i for i in items if q in (i["prompt"] + " " + i["style"]).lower()] if q else items


def delete_image(user, filename):
    if os.path.basename(filename) != filename:
        return
    try:
        os.remove(os.path.join(_dir(user), filename))
    except OSError:
        pass
    _write_index(user, [i for i in _index(user) if i["file"] != filename])


def delete_all(user):
    for i in list_images(user):
        delete_image(user, i["file"])


def render_gallery(user):
    st.subheader("🖼️ Jarvis AI Gallery")
    items = list_images(user)
    st.caption(f"{len(items)} saved image(s) · stored permanently in `{ROOT}/` · generated in chat or Image Studio.")
    if not items:
        st.info("No images yet. Try `/image a rocket launch at sunset` in chat.")
        return
    q = st.text_input("Search your images", placeholder="🔍 prompt or style…", label_visibility="collapsed")
    items = list_images(user, q)
    cols_n = 3
    for row in range(0, len(items), cols_n):
        cols = st.columns(cols_n)
        for col, it in zip(cols, items[row: row + cols_n]):
            data = load_image(user, it["file"])
            if not data:
                continue
            with col:
                st.image(data, use_container_width=True)
                st.caption(f"{it['style'] or 'image'} · {it['created'][:16].replace('T', ' ')}")
                with st.expander("Prompt"):
                    st.write(it["enhanced"] or it["prompt"])
                a, b = st.columns(2)
                a.download_button("⬇️", data, it["file"], key=f"gdl_{it['file']}", use_container_width=True)
                if b.button("🗑", key=f"gdel_{it['file']}", use_container_width=True):
                    delete_image(user, it["file"])
                    st.rerun()
