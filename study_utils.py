"""Study Hub: flashcards (spaced repetition), AI quizzes, homework solver, smart notes,
study log + streaks, exam countdowns."""
import copy
import json
import os
import time
from datetime import date, datetime, timedelta

import streamlit as st

from data_paths import path as _dp

INTERVAL_DAYS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}      # Leitner boxes -> days until next review

# ----------------------------- storage -----------------------------
# Every user gets a folder  jarvis_data/users/<User>/  with one readable JSON file per category
# and a plain-text copy (.txt) of the important ones. Writes are atomic (no half-saved files).
FILES = {"decks": "flashcards.json", "notes": "notes.json", "quizzes": "quizzes.json", "logs": "study_log.json",
         "exams": "exams.json", "syllabus": "syllabus.json", "plan": "study_plan.json", "routine": "daily_routine.json"}
_DEFAULTS = {"decks": {}, "notes": [], "quizzes": [], "logs": [], "exams": [], "syllabus": {}, "plan": {}, "routine": {}}
LEGACY_FILE = _dp("study_data.json")


def _safe(user):
    return "".join(c for c in user if c.isalnum() or c in "_- ") .strip() or "user"


def user_dir(user):
    return _dp("users", _safe(user), "")


def _read_json(p, default):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return copy.deepcopy(default)


def _write_text(p, text):
    """Atomic + only when the content changed."""
    try:
        if os.path.exists(p) and open(p, "r", encoding="utf-8").read() == text:
            return
    except Exception:
        pass
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)


def _write_json(p, obj):
    _write_text(p, json.dumps(obj, indent=2, ensure_ascii=False))


def load(user):
    base = user_dir(user)
    if not any(os.path.exists(os.path.join(base, f)) for f in FILES.values()):
        _migrate_legacy(user)
    return {k: _read_json(os.path.join(base, f), _DEFAULTS[k]) for k, f in FILES.items()}


def save(user, data):
    base = user_dir(user)
    for k, f in FILES.items():
        if k in data:
            _write_json(os.path.join(base, f), data[k])
    _write_mirrors(base, user, data)


def _migrate_legacy(user):
    """One-time import from the old single-file study_data.json."""
    old = _read_json(LEGACY_FILE, {}).get(user)
    if old:
        save(user, {**copy.deepcopy(_DEFAULTS), **{k: v for k, v in old.items() if k in FILES}})


# ----------------------------- readable .txt copies -----------------------------
def _hm12(hhmm):
    try:
        return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")
    except Exception:
        return hhmm


def txt_syllabus(user, d):
    out = [f"MY SYLLABUS - {user}", f"(saved {datetime.now():%d %b %Y %H:%M})", ""]
    for sub, v in d.get("syllabus", {}).items():
        out.append(f"== {sub} (Class {v.get('cls', '')}) {('- ' + v['book']) if v.get('book') else ''} ==")
        out += [f"  {i}. {c}" for i, c in enumerate(v.get("chapters", []), 1)] + [""]
    return "\n".join(out)


def txt_exams(user, d):
    out = [f"MY EXAMS - {user}", ""]
    for e in d.get("exams", []):
        done = sum(1 for c in e.get("chapters", []) if c.get("done"))
        out.append(f"## {e.get('name')} | {e.get('subject')} | {e.get('date')} {e.get('time', '')} | {e.get('marks', 80)} marks | {done}/{len(e.get('chapters', []))} chapters done")
        out += [f"   [{'x' if c.get('done') else ' '}] {c.get('subject', '')}: {c['name']}" for c in e.get("chapters", [])] + [""]
    return "\n".join(out)


def txt_plan(user, d):
    plan = d.get("plan") or {}
    out = [f"STUDY PLAN - {user}", f"(generated {plan.get('generated', '-')})", ""]
    for ds in sorted(plan.get("days", {})):
        out.append(f"-- {ds} --")
        out += [f"  {_hm12(i['t'])}{('-' + _hm12(i['end'])) if i.get('end') else ''}  {i['text']}" for i in plan["days"][ds]] + [""]
    return "\n".join(out)


def txt_notes(user, d):
    out = [f"MY NOTES - {user}", ""]
    for n in d.get("notes", []):
        out += [f"##### {n.get('title')}  ({n.get('date')})", n.get("body", ""), "", "-" * 60, ""]
    return "\n".join(out)


def txt_cards(user, d):
    out = [f"MY FLASHCARDS - {user}", ""]
    for name, cards in d.get("decks", {}).items():
        out.append(f"== {name} ({len(cards)} cards) ==")
        out += [f"  Q: {c['q']}\n  A: {c['a']}   [box {c.get('box', 1)}, due {c.get('due', '')}]\n" for c in cards]
    return "\n".join(out)


_MIRRORS = {"syllabus": ("syllabus.txt", txt_syllabus), "exams": ("exams.txt", txt_exams), "plan": ("study_plan.txt", txt_plan),
            "notes": ("notes.txt", txt_notes), "decks": ("flashcards.txt", txt_cards)}


def _write_mirrors(base, user, data):
    for key, (fname, fn) in _MIRRORS.items():
        if key in data:
            try:
                _write_text(os.path.join(base, fname), fn(user, data))
            except Exception:
                pass


def json_from(raw):
    """Pulls the first JSON array out of an LLM reply (handles code fences / chatter)."""
    return json.loads(raw[raw.index("["): raw.rindex("]") + 1])


def ask(client, model, prompt, system="You are Jarvis, an expert, friendly tutor for a Class 10 student (CBSE/ICSE level).",
        temperature=0.3):
    r = client.chat.completions.create(model=model, temperature=temperature,
                                       messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
    return r.choices[0].message.content


def reset(user, sections):
    """Danger Zone: wipe selected sections of a user's study data ('decks','notes','quizzes','logs','exams','plan','routine')."""
    d = load(user)
    for k in sections:
        d[k] = {} if k in ("decks", "plan", "routine", "syllabus") else []
    save(user, d)


# ----------------------------- study log / streak -----------------------------
def log_study(user, minutes, subject="General"):
    d = load(user)
    d["logs"].append({"date": date.today().isoformat(), "minutes": int(minutes), "subject": subject or "General"})
    save(user, d)


def streak_info(user):
    """-> (streak_days, minutes_today). Streak survives until the end of the day after your last study day."""
    logs = load(user)["logs"]
    days = {l["date"] for l in logs}
    today = date.today()
    cur = today if today.isoformat() in days else today - timedelta(days=1)
    streak = 0
    while cur.isoformat() in days:
        streak += 1
        cur -= timedelta(days=1)
    return streak, sum(l["minutes"] for l in logs if l["date"] == today.isoformat())


# ----------------------------- flashcards -----------------------------
def add_deck(user, name, cards):
    d = load(user)
    deck = d["decks"].setdefault(name, [])
    deck += [{"q": c["q"], "a": c["a"], "box": 1, "due": date.today().isoformat(), "last": 0} for c in cards]
    save(user, d)


def due_cards(user, deck):
    cards = load(user)["decks"].get(deck, [])
    today = date.today().isoformat()
    return sorted([(i, c) for i, c in enumerate(cards) if c["due"] <= today], key=lambda x: x[1]["last"])


def grade_card(user, deck, idx, ok):
    d = load(user)
    c = d["decks"][deck][idx]
    c["box"] = min(5, c["box"] + 1) if ok else 1
    c["due"] = (date.today() + timedelta(days=INTERVAL_DAYS[c["box"]])).isoformat()
    c["last"] = time.time()
    save(user, d)


def make_cards(client, model, source, n=10):
    raw = ask(client, model, f"Create {n} high-quality flashcards from this topic/notes. Reply with ONLY a JSON array of objects "
                             f'like {{"q":"question","a":"short precise answer"}}.\n\n{source[:6000]}')
    return [c for c in json_from(raw) if c.get("q") and c.get("a")]


# ----------------------------- UI -----------------------------
def _tab_flashcards(user, client, model):
    d = load(user)
    with st.expander("➕ Create flashcards", expanded=not d["decks"]):
        name = st.text_input("Deck name", "Trigonometry")
        import syllabus_utils as syl
        pick = st.selectbox("From my syllabus", [None] + syl.pairs(user), key="fc_pick",
                            format_func=lambda p: "- or type my own topic below -" if p is None else f"{p[0]} - {p[1]}")
        src = st.text_area("Extra notes / topic (optional)", placeholder="e.g. focus on formulas and word problems", height=80)
        n = st.slider("How many cards", 5, 20, 10)
        if st.button("✨ Generate with Jarvis", disabled=not (name and (pick or src.strip()))):
            with st.spinner("Writing flashcards..."):
                try:
                    cards = make_cards(client, model, (f"{pick[0]} - chapter: {pick[1]}\n" if pick else "") + src, n)
                    add_deck(user, name, cards)
                    st.success(f"Added {len(cards)} cards to '{name}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not generate cards: {e}")
    if not d["decks"]:
        return
    deck = st.selectbox("Deck", list(d["decks"]))
    cards = d["decks"][deck]
    due = due_cards(user, deck)
    c1, c2, c3 = st.columns(3)
    c1.metric("Cards", len(cards))
    c2.metric("Due today", len(due))
    c3.metric("Mastered (box 5)", sum(1 for c in cards if c["box"] == 5))
    if not due:
        st.success("🎉 All caught up for today! Come back tomorrow for the next reviews.")
    else:
        idx, card = due[0]
        st.markdown(f"#### ❓ {card['q']}")
        shown = st.session_state.get("fc_show") == (deck, idx)
        if not shown:
            if st.button("👀 Show answer", use_container_width=True, type="primary"):
                st.session_state.fc_show = (deck, idx)
                st.rerun()
        else:
            st.info(card["a"])
            a, b = st.columns(2)
            if a.button("✅ Got it", use_container_width=True):
                grade_card(user, deck, idx, True)
                st.session_state.fc_show = None
                st.rerun()
            if b.button("🔁 Again", use_container_width=True):
                grade_card(user, deck, idx, False)
                st.session_state.fc_show = None
                st.rerun()
    with st.expander("Manage deck"):
        for i, c in enumerate(cards):
            st.markdown(f"**{i + 1}.** {c['q']}  \n↳ {c['a']}  · box {c['box']}")
        if st.button("🗑 Delete this deck"):
            d["decks"].pop(deck)
            save(user, d)
            st.rerun()


def _tab_quiz(user, client, model):
    c1, c2, c3 = st.columns([3, 1, 1])
    import syllabus_utils as syl
    pr = syl.pairs(user)
    if pr:
        pick = c1.selectbox("Quiz topic (from my syllabus)", pr, format_func=lambda p: f"{p[0]} - {p[1]}", key="qz_topic")
        topic = f"{pick[1]} ({pick[0]})"
    else:
        topic = c1.text_input("Quiz topic", "Quadratic equations")
        c1.caption("Add your syllabus to pick from your own chapters.")
    n = c2.number_input("Questions", 3, 15, 5)
    level = c3.selectbox("Level", ["Easy", "Medium", "Hard"], index=1)
    if st.button("🎯 Start quiz", type="primary", disabled=not topic):
        with st.spinner("Preparing your quiz..."):
            try:
                raw = ask(client, model, f"Write {n} {level} multiple-choice questions on '{topic}' for a Class 10 student. Reply with ONLY a JSON "
                                         'array of objects: {"q":"...","options":["A","B","C","D"],"answer":0,"explain":"one-line reason"} '
                                         "where answer is the 0-based index of the correct option.")
                qs = [q for q in json_from(raw) if len(q.get("options", [])) == 4 and q.get("answer") in (0, 1, 2, 3)]
                st.session_state.quiz = {"topic": topic, "level": level, "qs": qs, "done": False}
                for k in list(st.session_state):
                    if str(k).startswith("qz_"):
                        del st.session_state[k]
            except Exception as e:
                st.error(f"Could not build the quiz: {e}")
    quiz = st.session_state.get("quiz")
    if quiz and quiz["qs"]:
        with st.form("quiz_form"):
            for i, q in enumerate(quiz["qs"]):
                st.markdown(f"**Q{i + 1}. {q['q']}**")
                st.radio("Choose", q["options"], index=None, key=f"qz_{i}", label_visibility="collapsed")
            submitted = st.form_submit_button("✅ Submit answers", use_container_width=True)
        if submitted and not quiz["done"]:
            score = sum(1 for i, q in enumerate(quiz["qs"]) if st.session_state.get(f"qz_{i}") == q["options"][q["answer"]])
            quiz["done"], quiz["score"] = True, score
            d = load(user)
            d["quizzes"].append({"date": date.today().isoformat(), "topic": quiz["topic"], "level": quiz["level"],
                                 "score": score, "total": len(quiz["qs"])})
            save(user, d)
        if quiz["done"]:
            pct = round(100 * quiz["score"] / len(quiz["qs"]))
            (st.success if pct >= 70 else st.warning)(f"Score: {quiz['score']}/{len(quiz['qs'])}  ({pct}%)")
            for i, q in enumerate(quiz["qs"]):
                ok = st.session_state.get(f"qz_{i}") == q["options"][q["answer"]]
                st.markdown(f"{'✅' if ok else '❌'} **Q{i + 1}** - answer: **{q['options'][q['answer']]}**  \n_{q.get('explain', '')}_")
            if st.button("🃏 Turn the questions I missed into flashcards"):
                missed = [{"q": q["q"], "a": f"{q['options'][q['answer']]} - {q.get('explain', '')}"} for i, q in enumerate(quiz["qs"])
                          if st.session_state.get(f"qz_{i}") != q["options"][q["answer"]]]
                if missed:
                    add_deck(user, f"Missed: {quiz['topic']}", missed)
                    st.success(f"Saved {len(missed)} cards.")


def _tab_solver(user, client, model, vmodel):
    q = st.text_area("Type your question", placeholder="e.g. Solve: 2x² - 7x + 3 = 0", height=100)
    img = st.file_uploader("…or upload a photo of the question", type=["png", "jpg", "jpeg"], key="solver_img")
    level = st.radio("Style", ["Step-by-step (simple)", "With theory & formula", "Final answer + quick check"], horizontal=True)
    if st.button("🧮 Solve", type="primary", disabled=not (q or img)):
        prompt = (f"Solve this for a Class 10 student. Style: {level}. Show clearly numbered steps, state formulas used, "
                  f"end with a bold **Final answer** and one common mistake to avoid.\n\n{q}")
        with st.spinner("Jarvis is working it out..."):
            try:
                if img:
                    from image_generation_and_pdf import ask_vision
                    ans = ask_vision(client, vmodel, prompt, img.getvalue(), img.type or "image/png")
                else:
                    ans = ask(client, model, prompt)
                st.markdown(ans)
            except Exception as e:
                st.error(f"Solver error: {e}")


def chapter_notes(client, model, cls, subject, book, chapter, level, depth, web):
    """Chapter notes from the NCERT book - grounded with live web snippets when enabled."""
    from web_tools import format_search_results, search_web
    grounding = ""
    if web:
        res = search_web(f"NCERT Class {cls} {subject} {chapter} chapter summary key points", 4)
        if res:
            grounding = "\n\nReference snippets from the web (may be incomplete - use only to cross-check facts):\n" + format_search_results(res)
    prompt = (f"Prepare {depth} for Class {cls}, subject: {subject}, book: {book}, chapter: **{chapter}**. Exam level: {level}.\n"
              "Follow the NCERT textbook and the current CBSE syllabus. Structure with markdown headings:\n"
              "1. Chapter at a glance (what it covers, main NCERT sections)\n2. Key concepts & definitions\n"
              "3. Formulas / laws / dates / diagrams to practise (use a table where helpful)\n"
              "4. Two solved examples typical for this exam level\n"
              "5. Important questions with answers or hints: MCQ, very short, short, long, case-based\n"
              "6. Common mistakes to avoid\n7. Memory tricks\n8. Exam strategy (say 'approx.' for any weightage)\n"
              "ACCURACY RULES: do not invent NCERT exercise numbers, page numbers, statistics or quotations; if unsure write "
              "'verify in the textbook'; keep every formula and unit correct." + grounding)
    return ask(client, model, prompt, temperature=0.2)


def _tab_notes(user, client, model):
    from ncert_data import LEVELS
    from exam_utils import NCERT_LINK, yt_url
    import syllabus_utils as syl
    d = load(user)
    subs = syl.subjects(user)
    subject = chapter = level = cls = book = None
    if not subs:
        st.info("📖 Notes are written only for chapters in **your syllabus**. Add it once - by typing, photo or PDF.")
        st.button("📖 Open My Syllabus", on_click=lambda: st.session_state.update(mode="Syllabus"), type="primary", key="nt_goto")
    else:
        c1, c2, c3 = st.columns(3)
        subject = c1.selectbox("Subject", subs, key="nt_sub")
        chapter = c2.selectbox("Chapter", syl.chapters_of(user, subject), key=f"nt_ch_{subject}")
        level = c3.selectbox("Exam level", LEVELS, index=1, key="nt_level")
        meta = syl.info(user, subject)
        cls, book = meta.get("cls", "10"), meta.get("book") or "NCERT"
        st.caption(f"📘 {book} · Class {cls} · chapters come only from your saved syllabus")
    d1, d2 = st.columns([2, 2])
    depth = d1.selectbox("Notes style", ["short revision notes", "standard chapter notes", "detailed notes with extra examples"], index=1)
    web = d2.toggle("Cross-check with live web", value=True, help="Adds web snippets so facts are verified, not just remembered.")
    if st.button("📘 Get notes - no pasting needed", type="primary", disabled=not (chapter and subject)):
        with st.spinner(f"Writing notes for {chapter}..."):
            try:
                md = chapter_notes(client, model, cls, subject, book, chapter, level, depth, web)
                md += (f"\n\n---\n📺 [Best videos for this chapter on YouTube]({yt_url(cls, subject, chapter, level)})  ·  "
                       f"📚 [NCERT textbooks]({NCERT_LINK})")
                st.session_state.note_out = {"title": f"Class {cls} {subject} - {chapter}", "md": md}
            except Exception as e:
                st.error(f"Could not write notes: {e}")
    out = st.session_state.get("note_out")
    if out:
        st.markdown(out["md"])
        a, b, c = st.columns(3)
        if a.button("💾 Save note", use_container_width=True):
            d["notes"].insert(0, {"title": out["title"], "date": date.today().isoformat(), "body": out["md"]})
            save(user, d)
            st.success("Saved.")
        if b.button("🃏 Make flashcards", use_container_width=True):
            try:
                cards = make_cards(client, model, out["md"], 12)
                add_deck(user, out["title"][:40], cards)
                st.success(f"{len(cards)} flashcards created.")
            except Exception as e:
                st.error(str(e))
        if c.button("📄 Build PDF", use_container_width=True):
            from image_generation_and_pdf import build_pdf
            st.session_state.note_pdf = build_pdf(out["title"], out["md"])
        if st.session_state.get("note_pdf"):
            st.download_button("⬇️ Download PDF", st.session_state.note_pdf, "notes.pdf", "application/pdf")

    with st.expander("…or use my own notes / a PDF instead"):
        up = st.file_uploader("Upload a PDF / text file", type=["pdf", "txt", "md"], key="notes_file")
        text = st.text_area("Paste notes", height=120, key="own_notes")
        if up:
            from image_generation_and_pdf import extract_pdf_text
            text = (text + "\n" + (extract_pdf_text(up.getvalue()) if up.type == "application/pdf"
                                    else up.getvalue().decode("utf-8", "ignore"))).strip()
        if st.button("✨ Summarize & make exam prep", disabled=not text):
            with st.spinner("Reading your notes..."):
                try:
                    md = ask(client, model, "From these notes produce: 1) a 5-line summary, 2) key terms, 3) all formulas, "
                                            "4) five likely exam questions with short model answers. Markdown headings.\n\n" + text[:9000], temperature=0.2)
                    st.session_state.note_out = {"title": "My notes", "md": md}
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    if d["notes"]:
        st.markdown("##### 📒 Saved notes")
        for i, n in enumerate(d["notes"]):
            with st.expander(f"{n['title']} · {n['date']}"):
                st.markdown(n["body"])
                a, b = st.columns(2)
                a.download_button("⬇️ .md", n["body"].encode(), f"{n['title']}.md", key=f"note_dl_{i}", use_container_width=True)
                if b.button("🗑 Delete", key=f"note_del_{i}", use_container_width=True):
                    d["notes"].pop(i)
                    save(user, d)
                    st.rerun()


def _tab_progress(user):
    d = load(user)
    streak, today_min = streak_info(user)
    week = {(date.today() - timedelta(days=i)).isoformat(): 0 for i in range(6, -1, -1)}
    for l in d["logs"]:
        if l["date"] in week:
            week[l["date"]] += l["minutes"]
    a, b, c = st.columns(3)
    a.metric("🔥 Streak", f"{streak} day{'s' if streak != 1 else ''}")
    b.metric("Today", f"{today_min} min")
    c.metric("Last 7 days", f"{sum(week.values()) / 60:.1f} h")
    st.bar_chart({datetime.fromisoformat(k).strftime("%a"): v for k, v in week.items()})
    with st.form("log_form", clear_on_submit=True):
        x, y = st.columns(2)
        mins, subj = x.number_input("Minutes studied", 5, 600, 30, 5), y.text_input("Subject", "Maths")
        if st.form_submit_button("➕ Log study time", use_container_width=True):
            log_study(user, mins, subj)
            st.rerun()
    by = {}
    for l in d["logs"]:
        by[l["subject"]] = by.get(l["subject"], 0) + l["minutes"]
    if by:
        st.markdown("**Time by subject (minutes)**")
        st.bar_chart(by)
    if d["quizzes"]:
        qs = d["quizzes"][-10:]
        avg = sum(100 * q["score"] / q["total"] for q in qs) / len(qs)
        st.markdown(f"**Quiz average (last {len(qs)}): {avg:.0f}%**")
        st.line_chart([round(100 * q["score"] / q["total"]) for q in qs])
    st.info("📅 Exams, chapters and the daily plan live in the **Exams & Planner** tab.")


def next_exam(user):
    ex = [e for e in load(user)["exams"] if e["date"] >= date.today().isoformat()]
    if not ex:
        return None
    e = min(ex, key=lambda e: e["date"])
    return e["name"], (date.fromisoformat(e["date"]) - date.today()).days


def render_study_hub(user, client, model, vmodel):
    st.subheader("📚 Study Hub")
    streak, today_min = streak_info(user)
    ne = next_exam(user)
    st.caption(f"🔥 {streak}-day streak · {today_min} min today" + (f" · next exam **{ne[0]}** in {ne[1]} days" if ne else ""))
    t1, t2, t3, t4, t5, t6 = st.tabs(["🃏 Flashcards", "🎯 Quiz", "🧮 Homework Solver", "📒 Smart Notes", "📅 Exams & Planner", "📈 Progress"])
    with t1:
        _tab_flashcards(user, client, model)
    with t2:
        _tab_quiz(user, client, model)
    with t3:
        _tab_solver(user, client, model, vmodel)
    with t4:
        _tab_notes(user, client, model)
    with t5:
        from exam_utils import render_exam_planner
        render_exam_planner(user, client, model)
    with t6:
        _tab_progress(user)
