"""Action Hub: PDFs (study sheets, chat transcripts), AI images, image/PDF Q&A."""
import base64
import io
import random
import urllib.parse
import urllib.request

import streamlit as st
from fpdf import FPDF

from gallery_utils import save_image

_REPL = {"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
         "\u2022": "-", "\u2026": "...", "\u00a0": " ", "\u2192": "->", "\u00d7": "x"}


def _latin(text):
    for k, v in _REPL.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")   # built-in PDF fonts are latin-1 only


class _PDF(FPDF):
    def __init__(self, title):
        super().__init__()
        self.doc_title = _latin(title)
        self.set_auto_page_break(True, 16)

    def header(self):
        self.set_fill_color(10, 14, 30)
        self.rect(0, 0, 210, 14, "F")
        self.set_text_color(0, 229, 255)
        self.set_font("Helvetica", "B", 10)
        self.set_y(4)
        self.cell(0, 6, "JARVIS  //  " + self.doc_title[:70], new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(20, 20, 20)
        self.set_y(20)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def build_pdf(title, body):
    """Tiny markdown subset: '# ' headings, '- ' bullets, ``` code blocks."""
    pdf = _PDF(title)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 9, _latin(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    code = False
    for raw in _latin(body).splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            code = not code
            continue
        if code:
            pdf.set_font("Courier", size=9)
            pdf.multi_cell(0, 5, line or " ", new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("#"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 7, line.lstrip("# ").strip(), new_x="LMARGIN", new_y="NEXT")
        elif line.lstrip().startswith(("- ", "* ")):
            pdf.set_font("Helvetica", size=11)
            pdf.set_x(14)
            pdf.multi_cell(0, 6, "-  " + line.lstrip()[2:].replace("**", ""), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(0, 6, line.replace("**", "") or " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def chat_to_pdf(messages, title="Jarvis Conversation"):
    body = []
    for m in messages:
        body.append("# " + ("You" if m["role"] == "user" else "Jarvis"))
        body.append(m["content"])
        body.append("")
    return build_pdf(title, "\n".join(body))


STYLES = {
    "Cinematic": "cinematic still, dramatic lighting, shallow depth of field, rich colour grading, 35mm film, highly detailed",
    "Photorealistic": "ultra realistic photograph, natural light, 85mm lens, sharp focus, fine detail, 8k",
    "Anime": "high quality anime illustration, clean line art, vibrant colours, detailed background, studio quality",
    "3D Render": "3D render, octane render, soft global illumination, smooth materials, high detail",
    "Digital Art": "polished digital painting, concept art, intricate detail, artstation trending, balanced composition",
    "Neon Cyberpunk": "cyberpunk, neon lights, rain-soaked streets, volumetric fog, glowing reflections, highly detailed",
    "Watercolor": "delicate watercolor painting, soft washes, paper texture, gentle colours",
    "Pencil Sketch": "detailed graphite pencil sketch, cross-hatching, white paper, professional illustration",
}
_NEGATIVE = "no text, no letters, no watermark, no logo, no extra fingers, no distorted anatomy, no blur"


def enhance_prompt(client, model, idea, style="Cinematic"):
    """Turns a short idea into a detailed prompt - this is what stops 'waste' images."""
    suffix = STYLES.get(style, "")
    if client is not None:
        try:
            r = client.chat.completions.create(model=model, temperature=0.7, messages=[
                {"role": "system", "content": "You write prompts for text-to-image models. Reply with ONE English paragraph under 70 words "
                 "describing: main subject, setting, composition and camera angle, lighting, mood, colour palette. Be concrete and visual. "
                 "Never include words to be written in the image. No preface, no quotes."},
                {"role": "user", "content": f"Idea: {idea}\nStyle: {style}"}])
            core = (r.choices[0].message.content or "").strip().strip('"')
            if len(core) > 20:
                return f"{core}, {suffix}, {_NEGATIVE}"
        except Exception:
            pass
    return f"{idea}, {suffix}, {_NEGATIVE}"


def generate_image(prompt, width=1024, height=1024, seed=None, model="flux", retries=2):
    """Pollinations text-to-image with retries and a fallback model. Returns image bytes."""
    last = None
    for attempt in range(retries + 1):
        use_model = model if attempt < retries else "turbo"
        sd = seed if (seed is not None and attempt == 0) else random.randint(1, 10**6)
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
               f"?width={width}&height={height}&seed={sd}&model={use_model}&nologo=true&private=true")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
                if "image" in r.headers.get("Content-Type", "") and len(data) > 8000:
                    return data
                last = "service returned an invalid image"
        except Exception as e:
            last = str(e)
    raise RuntimeError(f"Image generation failed: {last}")


def create_image(client, model, idea, style="Cinematic", width=1024, height=1024, enhance=True, seed=None):
    """Full pipeline -> (image_bytes, final_prompt)."""
    final = enhance_prompt(client if enhance else None, model, idea, style)
    return generate_image(final, width, height, seed), final


def extract_pdf_text(pdf_bytes, max_chars=12000):
    try:
        from pypdf import PdfReader
    except ImportError:
        return "[Install pypdf to read PDFs: pip install pypdf]"
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:25])
    return text[:max_chars] or "[No selectable text found - this PDF may be a scan.]"


def image_message(text, image_bytes, mime="image/png"):
    url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
    return {"role": "user", "content": [{"type": "text", "text": text},
                                        {"type": "image_url", "image_url": {"url": url}}]}


def ask_vision(client, model, question, image_bytes, mime="image/png"):
    r = client.chat.completions.create(model=model, messages=[image_message(question, image_bytes, mime)])
    return r.choices[0].message.content


def ask_text(client, model, prompt, system="You are Jarvis, a precise study assistant."):
    r = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system},
                                                              {"role": "user", "content": prompt}])
    return r.choices[0].message.content


def render_image_module(client=None, model="", vision_model="", messages=None, perms=None, username="", stamp=True):
    """`perms` = set-like check function (has_permission bound to the user's role)."""
    can = perms or (lambda p: True)
    st.subheader("🛠️ Action Hub")
    t_pdf, t_chat, t_img, t_qa = st.tabs(["📄 Study PDF", "💬 Chat → PDF", "🎨 Image Studio", "🔍 Image / PDF Q&A"])

    with t_pdf:
        if not can("pdf"):
            st.warning("Your role cannot create PDFs.")
        else:
            title = st.text_input("Document title", "Class 10 Mathematics - Circle Theorems Reference")
            content = st.text_area("Content (supports # headings, - bullets)", height=170,
                                   value="# Key facts\n- Tangent is perpendicular to the radius.\n- Tangents from an external point are equal.")
            c1, c2 = st.columns(2)
            if c1.button("📥 Build PDF", use_container_width=True):
                st.session_state.hub_pdf = (title, build_pdf(title, content))
            if c2.button("✨ Let Jarvis write it", use_container_width=True, disabled=client is None):
                with st.spinner("Jarvis is writing your study sheet..."):
                    try:
                        text = ask_text(client, model, f"Write a concise, well-structured study sheet about: {title}. "
                                        "Use '# ' headings and '- ' bullets only. Include formulas and 2 worked examples.")
                        st.session_state.hub_pdf = (title, build_pdf(title, text))
                        st.markdown(text)
                    except Exception as e:
                        st.error(f"AI error: {e}")
            if "hub_pdf" in st.session_state:
                name, data = st.session_state.hub_pdf
                st.download_button("⬇️ Download PDF", data, f"{name[:40].strip().replace(' ', '_')}.pdf", "application/pdf")

    with t_chat:
        msgs = [m for m in (messages or []) if m.get("content")]
        if not msgs:
            st.info("Chat with Jarvis first - then export the conversation here.")
        else:
            st.caption(f"{len(msgs)} messages in the current session.")
            if st.button("📄 Compile transcript PDF", use_container_width=True):
                st.session_state.hub_chat_pdf = chat_to_pdf(msgs)
            if "hub_chat_pdf" in st.session_state:
                st.download_button("⬇️ Download transcript", st.session_state.hub_chat_pdf, "Jarvis_Transcript.pdf", "application/pdf")

    with t_img:
        if not can("image"):
            st.warning("Your role cannot generate images.")
        else:
            idea = st.text_area("Describe the image", placeholder="a boy studying physics on a rooftop at sunset, city lights below")
            c1, c2 = st.columns(2)
            style = c1.selectbox("Style", list(STYLES), index=0)
            size = c2.selectbox("Size", ["Square 1024x1024", "Landscape 1280x720", "Portrait 720x1280"])
            w, h = {"Square 1024x1024": (1024, 1024), "Landscape 1280x720": (1280, 720), "Portrait 720x1280": (720, 1280)}[size]
            c3, c4 = st.columns(2)
            enhance = c3.toggle("✨ Let Jarvis improve my prompt", value=client is not None, disabled=client is None,
                                help="Rewrites a short idea into a detailed prompt - the biggest quality boost.")
            count = c4.slider("Variations", 1, 3, 2)
            if st.button("🎨 Generate", type="primary", disabled=not idea):
                imgs, final = [], ""
                bar = st.progress(0.0, "Jarvis is painting...")
                for i in range(count):
                    try:
                        data, final = create_image(client, model, idea, style, w, h, enhance, seed=None)
                        if username:   # saved permanently + stamped 'JARVIS AI'
                            _, data = save_image(username, data, idea, final, style, stamp=stamp)
                        imgs.append(data)
                    except Exception as e:
                        st.error(str(e))
                        break
                    bar.progress((i + 1) / count, f"Image {i + 1}/{count} ready")
                bar.empty()
                st.session_state.hub_images, st.session_state.hub_prompt = imgs, final
            if st.session_state.get("hub_images"):
                st.caption("✅ Saved to your Gallery (sidebar → Gallery).")
                with st.expander("Prompt used"):
                    st.write(st.session_state.hub_prompt)
                cols = st.columns(len(st.session_state.hub_images))
                for i, (col, data) in enumerate(zip(cols, st.session_state.hub_images)):
                    col.image(data)
                    col.download_button("⬇️ Save", data, f"jarvis_image_{i + 1}.png", "image/png", key=f"hub_dl_{i}")

    with t_qa:
        if not can("vision") or client is None:
            st.warning("Vision is unavailable for your role or no model is configured.")
        else:
            up = st.file_uploader("Upload a screenshot, diagram, photo or PDF", type=["png", "jpg", "jpeg", "pdf"], key="hub_qa_file")
            q = st.text_input("What should Jarvis do with it?", "Summarize this and list the key points.")
            if up and st.button("🔍 Analyze", type="primary"):
                with st.spinner("Jarvis is reading..."):
                    try:
                        data = up.getvalue()
                        if up.type == "application/pdf":
                            ans = ask_text(client, model, f"{q}\n\n--- DOCUMENT ---\n{extract_pdf_text(data)}")
                        else:
                            st.image(data, width=360)
                            ans = ask_vision(client, vision_model or model, q, data, up.type or "image/png")
                        st.markdown(ans)
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
