"""My Syllabus: the single source of truth for chapters.
Add it by typing, by photo(s) of the syllabus/index page, from a PDF, or (optionally) from an NCERT list.
Exams, notes, quizzes and plans use ONLY what is saved here."""
import os
import re
import uuid

import streamlit as st

import study_utils as su
from ncert_data import CLASSES, NCERT

from data_paths import path as _dp

FILES_DIR = _dp("syllabus_files")


# ----------------------------- storage -----------------------------
def get_syllabus(user):
    return su.load(user)["syllabus"]


def subjects(user):
    return list(get_syllabus(user))


def chapters_of(user, subject):
    return list(get_syllabus(user).get(subject, {}).get("chapters", []))


def info(user, subject):
    return get_syllabus(user).get(subject, {"book": "", "cls": "10", "chapters": []})


def pairs(user):
    """[(subject, chapter)] for everything in the syllabus."""
    return [(s, c) for s, v in get_syllabus(user).items() for c in v["chapters"]]


def parse_lines(text):
    """Splits typed/pasted text into clean chapter names (drops '1.', 'Ch 3:', bullets; de-duplicates)."""
    out, seen = [], set()
    for part in re.split(r"[\n;]+|,\s(?=[A-Z0-9])", text or ""):
        name = re.sub(r"^\s*(?:[-*•]+|(?:chapter|ch\.?|unit|lesson)?\s*\d{1,2}\s*[\).:\-–]+)\s*", "", part, flags=re.I).strip(" .\t")
        if len(name) >= 2 and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def save_subject(user, subject, chapters, book="", cls="10"):
    d = su.load(user)
    s = d["syllabus"].setdefault(subject, {"book": book, "cls": cls, "chapters": []})
    s["book"], s["cls"] = book or s.get("book", ""), cls
    have = {c.lower() for c in s["chapters"]}
    added = [c for c in chapters if c.lower() not in have]
    s["chapters"] += added
    su.save(user, d)
    return len(added)


def remove_chapter(user, subject, name):
    d = su.load(user)
    if subject in d["syllabus"]:
        d["syllabus"][subject]["chapters"] = [c for c in d["syllabus"][subject]["chapters"] if c != name]
        su.save(user, d)


def delete_subject(user, subject):
    d = su.load(user)
    d["syllabus"].pop(subject, None)
    su.save(user, d)


# ----------------------------- uploaded files -----------------------------
def _dir(user):
    p = os.path.join(FILES_DIR, "".join(c for c in user if c.isalnum() or c in "_-") or "user")
    os.makedirs(p, exist_ok=True)
    return p


def save_upload(user, subject, filename, data):
    ext = os.path.splitext(filename)[1].lower() or ".png"
    name = f"{re.sub(r'[^A-Za-z0-9]+', '_', subject)[:20]}_{uuid.uuid4().hex[:6]}{ext}"
    with open(os.path.join(_dir(user), name), "wb") as f:
        f.write(data)
    return name


def list_uploads(user):
    return sorted(os.listdir(_dir(user)))


def read_upload(user, name):
    if os.path.basename(name) != name:
        return None
    p = os.path.join(_dir(user), name)
    return open(p, "rb").read() if os.path.exists(p) else None


def delete_upload(user, name):
    if os.path.basename(name) == name:
        try:
            os.remove(os.path.join(_dir(user), name))
        except OSError:
            pass


# ----------------------------- extraction -----------------------------
_IMG_PROMPT = ("This is a photo of a school syllabus, textbook index or table of contents. List EVERY chapter / unit / topic name exactly "
               "as printed, in order. Reply with ONLY a JSON array of strings. Skip anything you cannot read - never invent chapters.")


def extract_from_images(client, vmodel, files):
    from image_generation_and_pdf import ask_vision
    found = []
    for f in files:
        raw = ask_vision(client, vmodel, _IMG_PROMPT, f.getvalue(), f.type or "image/png")
        try:
            found += [str(x) for x in su.json_from(raw)]
        except Exception:
            found += parse_lines(raw)
    return parse_lines("\n".join(found))


def extract_from_pdf(client, model, pdf_bytes):
    from image_generation_and_pdf import extract_pdf_text
    text = extract_pdf_text(pdf_bytes, 9000)
    raw = su.ask(client, model, "From this syllabus / book index text, list every chapter or unit name in order. Reply with ONLY a JSON array "
                                "of strings. Never invent chapters.\n\n" + text, temperature=0.0)
    try:
        return parse_lines("\n".join(str(x) for x in su.json_from(raw)))
    except Exception:
        return parse_lines(raw)


# ----------------------------- page -----------------------------
def _goto(mode):
    st.session_state.mode = mode


def render_syllabus_page(user, client, model, vmodel):
    st.subheader("📖 My Syllabus")
    st.caption("Add it once - typing, photo, or PDF. Exams, notes, quizzes and your study plan use ONLY these chapters.")
    st.caption(f"💾 Saved automatically in `{su.user_dir(user)}syllabus.json` and `syllabus.txt` (photos: `jarvis_data/syllabus_files/`).")
    syl = get_syllabus(user)
    a, b, c = st.columns(3)
    a.metric("Subjects", len(syl))
    b.metric("Chapters", sum(len(v["chapters"]) for v in syl.values()))
    c.metric("Photos / files saved", len(list_uploads(user)))
    t_add, t_my = st.tabs(["➕ Add / Import", "📚 My Syllabus"])

    with t_add:
        c1, c2, c3 = st.columns([1, 2, 2])
        cls = c1.selectbox("Class", CLASSES, index=CLASSES.index("10"), key="syl_cls")
        opts = list(syl) + [s for s in NCERT.get(cls, {}) if s not in syl] + ["✏️ New subject…"]
        pick = c2.selectbox("Subject", opts, key=f"syl_sub_{cls}")
        subject = st.text_input("New subject name", key="syl_newsub") if pick == "✏️ New subject…" else pick
        book = c3.text_input("Book name (optional)", value=syl.get(subject, {}).get("book") or NCERT.get(cls, {}).get(subject, {}).get("book", ""),
                             key=f"syl_book_{subject}")
        method = st.radio("How do you want to add chapters?", ["⌨️ Type", "📷 Photo(s)", "📄 PDF", "📘 NCERT list"], horizontal=True, key="syl_method")
        n = st.session_state.setdefault("syl_n", 0)

        if method == "⌨️ Type":
            typed = st.text_area("Type or paste chapters (one per line, or comma-separated)", height=130, key="syl_typed",
                                 placeholder="Real Numbers\nPolynomials\nPair of Linear Equations in Two Variables")
            if st.button("Use these chapters", disabled=not typed.strip()):
                st.session_state.syl_found, st.session_state.syl_n = parse_lines(typed), n + 1
                st.rerun()
        elif method == "📷 Photo(s)":
            files = st.file_uploader("Take / choose photo(s) of your syllabus or book index", type=["png", "jpg", "jpeg"],
                                     accept_multiple_files=True, key="syl_photos")
            if st.button("🔍 Read chapters from the photo(s)", disabled=not (files and subject), type="primary"):
                with st.spinner("Jarvis is reading your syllabus..."):
                    try:
                        found = extract_from_images(client, vmodel, files)
                        for f in files:
                            save_upload(user, subject, f.name, f.getvalue())
                        st.session_state.syl_found, st.session_state.syl_n = found, n + 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not read the photo: {e}")
        elif method == "📄 PDF":
            pdf = st.file_uploader("Upload a syllabus / index PDF", type=["pdf"], key="syl_pdf")
            if st.button("🔍 Read chapters from the PDF", disabled=not (pdf and subject), type="primary"):
                with st.spinner("Reading PDF..."):
                    try:
                        found = extract_from_pdf(client, model, pdf.getvalue())
                        save_upload(user, subject, pdf.name, pdf.getvalue())
                        st.session_state.syl_found, st.session_state.syl_n = found, n + 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not read the PDF: {e}")
        else:
            lst = NCERT.get(cls, {}).get(subject, {}).get("chapters")
            if lst:
                st.caption("Shortcut only - you can edit the list before saving.")
                if st.button(f"Load the NCERT list for {subject}"):
                    st.session_state.syl_found, st.session_state.syl_n = list(lst), n + 1
                    st.rerun()
            else:
                st.info("No built-in list for this class/subject - use Type, Photo or PDF.")

        found = st.session_state.get("syl_found")
        if found:
            st.markdown("##### ✅ Review - edit freely, one chapter per line")
            edited = st.text_area("Chapters to save", "\n".join(found), height=220, key=f"syl_review_{st.session_state.syl_n}")
            if st.button(f"💾 Save to {subject or 'syllabus'}", type="primary", disabled=not subject):
                added = save_subject(user, subject, parse_lines(edited), book, cls)
                st.session_state.syl_found = None
                st.success(f"Saved {added} new chapter(s) to {subject}.")
                st.rerun()

    with t_my:
        if not syl:
            st.info("Nothing here yet - add your first subject in the **Add / Import** tab.")
        for subj, v in syl.items():
            with st.expander(f"📘 {subj} · {len(v['chapters'])} chapters" + (f" · {v['book']}" if v.get("book") else "")):
                for i, ch in enumerate(v["chapters"], 1):
                    x, y = st.columns([9, 1])
                    x.markdown(f"**{i}.** {ch}")
                    if y.button("✕", key=f"syl_rm_{subj}_{i}", help="Remove chapter"):
                        remove_chapter(user, subj, ch)
                        st.rerun()
                p, q = st.columns([4, 1])
                extra = p.text_input("Add a chapter", key=f"syl_add_{subj}", label_visibility="collapsed", placeholder="Add a chapter…")
                if q.button("➕", key=f"syl_addb_{subj}") and extra.strip():
                    save_subject(user, subj, [extra.strip()], v.get("book", ""), v.get("cls", "10"))
                    st.rerun()
                if st.button(f"🗑 Delete subject '{subj}'", key=f"syl_del_{subj}"):
                    delete_subject(user, subj)
                    st.rerun()
        files = list_uploads(user)
        if files:
            with st.expander(f"🖼️ Saved syllabus photos & files ({len(files)})"):
                cols = st.columns(3)
                for i, f in enumerate(files):
                    with cols[i % 3]:
                        data = read_upload(user, f)
                        if f.lower().endswith((".png", ".jpg", ".jpeg")) and data:
                            st.image(data, use_container_width=True)
                        else:
                            st.caption(f"📄 {f}")
                        if st.button("🗑", key=f"syl_f_{f}"):
                            delete_upload(user, f)
                            st.rerun()
