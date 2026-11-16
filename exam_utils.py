"""Exam planner: multi-subject exams built ONLY from your saved syllabus, chapter tracking, daily routine + extra
daily reminders, an auto study plan (every chapter done >= 1 day before its exam), YouTube links, practice papers,
and the chat commands "what to study next" / "make a time table"."""
import csv
import io
import re
import urllib.parse
import uuid
from datetime import date, datetime, timedelta

import streamlit as st

import study_utils as su
import syllabus_utils as syl
from ncert_data import LEVELS, PAPER_80
from time_utils import now_ist
from web_tools import search_web

NCERT_LINK = "https://ncert.nic.in/textbook.php"
DEFAULT_ROUTINE = {
    "wake": "06:00", "breakfast": "07:15", "school_start": "08:00", "school_end": "15:00", "home": "15:45",
    "study1_start": "16:30", "study1_end": "18:00", "free_start": "18:00", "free_end": "19:00",
    "study2_start": "19:00", "study2_end": "20:30", "dinner": "20:30", "rev_start": "21:00", "rev_end": "21:30",
    "sleep": "22:00", "lunch": "13:00", "wk1_start": "09:00", "wk1_end": "10:30", "wk2_start": "11:00", "wk2_end": "12:30",
    "morning_start": "06:15", "morning_end": "07:00", "extras": [],
}
DAY_OPTS = ["Every day", "Weekdays", "Weekends"]
_LEVEL_HINT = {LEVELS[0]: "NCERT explanation", LEVELS[1]: "CBSE board exam important questions", LEVELS[2]: "HOTS case based questions",
               LEVELS[3]: "olympiad advanced problems", LEVELS[4]: "one shot revision"}


# ----------------------------- helpers -----------------------------
def _hm(hhmm):
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _fdate(iso):
    return date.fromisoformat(iso).strftime("%a %d %b")


def _strip_emoji(t):
    return re.sub(r"^[^A-Za-z(]+", "", t)


def yt_url(cls, subject, chapter, level):
    q = f"Class {cls} {subject} {chapter} {_LEVEL_HINT.get(level, '')}"
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)


def find_videos(cls, subject, chapter, level, n=3):
    q = f"site:youtube.com/watch Class {cls} {subject} {chapter} {_LEVEL_HINT.get(level, '')}"
    return [{"title": r["title"], "url": r["url"]} for r in search_web(q, 8)
            if "youtube.com/watch" in r["url"] or "youtu.be/" in r["url"]][:n]


def subj_label(e):
    return ", ".join(e.get("subjects") or [e.get("subject", "")])


def _csub(e, c):
    return c.get("subject") or e.get("subject", "")


# ----------------------------- exam storage -----------------------------
def get_exams(user):
    d = su.load(user)
    changed = False
    for e in d["exams"]:
        for k, v in (("id", None), ("subject", ""), ("cls", "10"), ("level", LEVELS[1]), ("book", ""),
                     ("time", "09:00"), ("marks", 80), ("chapters", [])):
            if k not in e:
                e[k] = uuid.uuid4().hex[:6] if k == "id" else v
                changed = True
        for c in e["chapters"]:
            if "subject" not in c:
                c["subject"] = e["subject"]
                changed = True
        subs = list(dict.fromkeys(c["subject"] for c in e["chapters"] if c["subject"])) or ([e["subject"]] if e["subject"] else [])
        if e.get("subjects") != subs:
            e["subjects"], e["subject"] = subs, ", ".join(subs)
            changed = True
    if changed:
        su.save(user, d)
    return d["exams"]


def _mutate(user, fn):
    get_exams(user)
    d = su.load(user)
    fn(d)
    su.save(user, d)
    if d.get("plan"):
        build_plan(user)          # keep the plan in sync with progress


def add_exam(user, exam):
    exam = {**exam, "id": uuid.uuid4().hex[:6]}
    _mutate(user, lambda d: d["exams"].append(exam))


def delete_exam(user, eid):
    _mutate(user, lambda d: d.__setitem__("exams", [e for e in d["exams"] if e["id"] != eid]))


def set_chapter(user, eid, idx, done):
    def f(d):
        for e in d["exams"]:
            if e["id"] == eid:
                e["chapters"][idx]["done"] = done
    _mutate(user, f)


def add_chapter(user, eid, subject, name):
    def f(d):
        for e in d["exams"]:
            if e["id"] == eid and not any(c["name"] == name and c["subject"] == subject for c in e["chapters"]):
                e["chapters"].append({"name": name, "subject": subject, "done": False})
    _mutate(user, f)
    get_exams(user)


def progress(e):
    return sum(1 for c in e["chapters"] if c["done"]), len(e["chapters"])


def days_left(e):
    return (date.fromisoformat(e["date"]) - date.today()).days


def upcoming(user, within=30):
    return sorted([e for e in get_exams(user) if 0 <= days_left(e) <= within], key=lambda e: (e["date"], e["time"]))


# ----------------------------- plan builder -----------------------------
def _slots(R, weekend, boost):
    s = [(R["study1_start"], R["study1_end"]), (R["study2_start"], R["study2_end"])]
    if weekend:
        return [(R["wk1_start"], R["wk1_end"]), (R["wk2_start"], R["wk2_end"])] + s
    return ([(R["morning_start"], R["morning_end"])] + s) if boost else s


def _extras(R, weekend):
    out = []
    for x in R.get("extras", []):
        if x["days"] == "Every day" or (x["days"] == "Weekdays" and not weekend) or (x["days"] == "Weekends" and weekend):
            out.append((x["t"], None, f"⏰ {x['text']}", "routine"))
    return out


def _routine_items(R, weekend):
    it = [(R["wake"], None, "⏰ Wake up - freshen up, light exercise / stretching", "routine"),
          (R["breakfast"], None, "🍳 Breakfast" + ("" if weekend else " & get ready for school"), "routine")]
    if weekend:
        it.append((R["lunch"], None, "🍛 Lunch & rest", "routine"))
    else:
        it += [(R["school_start"], R["school_end"], "🏫 School time", "routine"),
               (R["school_end"], None, "🚌 School over - head home", "routine"),
               (R["home"], None, "🏠 Back home - freshen up, lunch / snack & rest", "routine")]
    it += [(R["free_start"], R["free_end"], "🎮 Free time - play, hobby, family", "free"),
           (R["dinner"], None, "🍽️ Time for dinner", "routine"),
           (R["sleep"], None, "😴 Time to sleep - phone off (7-8 hours helps memory!)", "routine")]
    return it + _extras(R, weekend)


def _routine(user):
    return {**DEFAULT_ROUTINE, **su.load(user).get("routine", {})}


def _build(user, boost, horizon_cap=90):
    R, today = _routine(user), date.today()
    exams = sorted([e for e in get_exams(user) if date.fromisoformat(e["date"]) >= today], key=lambda e: e["date"])
    plan = {"generated": datetime.now().isoformat(timespec="minutes"), "days": {}, "late": [], "boosted": boost}
    if not exams:
        return plan
    end = min(max(date.fromisoformat(e["date"]) for e in exams), today + timedelta(days=horizon_cap))
    pending = []
    for e in exams:     # every chapter must be learned at least 1 day BEFORE its exam
        dl = max(today, date.fromisoformat(e["date"]) - timedelta(days=1))
        pending += [(dl, e, i) for i, c in enumerate(e["chapters"]) if not c["done"]]
    pending.sort(key=lambda x: x[0])      # earliest deadline first = as fast as possible
    rev, day, now_min = {}, today, now_ist().hour * 60 + now_ist().minute
    while day <= end:
        weekend = day.weekday() >= 5
        items = [{"t": a, "end": b, "text": t, "kind": k} for a, b, t, k in _routine_items(R, weekend)]
        items.append({"t": R["rev_start"], "end": R["rev_end"], "kind": "revision",
                      "text": "🧠 Quick recap - flashcards, formulas & tomorrow's plan"})
        near = sorted([e for e in exams if 0 <= (date.fromisoformat(e["date"]) - day).days <= 2], key=lambda e: e["date"])
        exam_today = False
        for e in near:
            if e["date"] == day.isoformat():
                exam_today = True
                items.append({"t": e["time"], "end": None, "kind": "exam", "exam": e["name"], "subject": e["subject"],
                              "text": f"📝 EXAM: {e['name']} ({e['subject']}) - stay calm, all the best!"})
        if not exam_today:
            for k, (a, b) in enumerate(_slots(R, weekend, boost)):
                if day == today and _mins(a) <= now_min:
                    continue
                rs = [e for e in near if 1 <= (date.fromisoformat(e["date"]) - day).days <= 2]
                if rs:
                    e, dt = rs[0], (date.fromisoformat(rs[0]["date"]) - day).days
                    if not any(p[1]["id"] == e["id"] for p in pending):     # all its chapters are already done
                        if dt == 2 and k == 0:
                            items.append({"t": a, "end": b, "kind": "study", "exam": e["name"], "subject": e["subject"],
                                          "text": f"📝 Timed practice paper - {e['subject']} ({e['marks']} marks, real exam timing)"})
                            continue
                        if dt == 1:
                            items.append({"t": a, "end": b, "kind": "study", "exam": e["name"], "subject": e["subject"],
                                          "text": f"🔁 Final revision - {e['subject']}: formulas, short notes, weak chapters"})
                            continue
                if pending:
                    dl, e, i = pending.pop(0)
                    c = e["chapters"][i]
                    sub = _csub(e, c)
                    if day > dl:
                        plan["late"].append(f"{sub}: {c['name']}")
                    items.append({"t": a, "end": b, "kind": "study", "exam": e["name"], "exam_id": e["id"], "ci": i, "subject": sub,
                                  "chapter": c["name"], "yt": yt_url(e["cls"], sub, c["name"], e["level"]),
                                  "text": f"📖 {sub}: {c['name']} - read NCERT (45 min) → exercises (30 min) → recap (15 min)"})
                else:
                    e0 = next((e for e in exams if date.fromisoformat(e["date"]) >= day and e["chapters"]), None)
                    if e0:
                        n = rev.get(e0["id"], 0)
                        rev[e0["id"]] = n + 1
                        c = e0["chapters"][n % len(e0["chapters"])]
                        sub = _csub(e0, c)
                        items.append({"t": a, "end": b, "kind": "study", "exam": e0["name"], "subject": sub, "chapter": c["name"],
                                      "yt": yt_url(e0["cls"], sub, c["name"], e0["level"]),
                                      "text": f"🔁 Revise {sub}: {c['name']} + solve 10 sample / previous-year questions"})
        items.sort(key=lambda x: _mins(x["t"]))
        plan["days"][day.isoformat()] = items
        day += timedelta(days=1)
    plan["late"] += [f"{_csub(e, e['chapters'][i])}: {e['chapters'][i]['name']}" for _, e, i in pending]
    return plan


def build_plan(user):
    """Normal plan first; if chapters would miss their deadline, automatically add an early-morning block."""
    plan = _build(user, False)
    if plan["late"]:
        alt = _build(user, True)
        if len(alt["late"]) < len(plan["late"]):
            plan = alt
    d = su.load(user)
    d["plan"] = plan
    su.save(user, d)
    return plan


def day_items(user, d=None):
    """Items for a date: the saved plan, or (no plan yet) just the daily routine + extras - so reminders/emails always work."""
    d = d or date.today()
    plan = su.load(user).get("plan") or {}
    if d.isoformat() in plan.get("days", {}):
        return plan["days"][d.isoformat()]
    R, weekend = _routine(user), d.weekday() >= 5
    items = [{"t": a, "end": b, "text": t, "kind": k} for a, b, t, k in _routine_items(R, weekend)]
    return sorted(items, key=lambda x: _mins(x["t"]))


plan_for_day = day_items


def due_plan_items(user):
    now = now_ist()
    fired = st.session_state.setdefault("fired_plan", set())
    cur, out = now.hour * 60 + now.minute, []
    for it in day_items(user):
        if 0 <= cur - _mins(it["t"]) < 3:
            key = f"{now:%Y-%m-%d}-{it['t']}-{it['text']}"
            if key not in fired:
                fired.add(key)
                out.append(_strip_emoji(it["text"]))
    return out


# ----------------------------- text outputs (chat / email) -----------------------------
def _link(it):
    return f" · [▶️ videos]({it['yt']})" if it.get("yt") else ""


def today_plan_markdown(user):
    items = day_items(user)
    return ("**Today's plan**\n" + "\n".join(f"- {_hm(i['t'])} {i['text']}{_link(i)}" for i in items)) if items else ""


def next_to_study_text(user):
    ex = upcoming(user, 30)
    if not ex:
        return ("📭 No exams in the next 30 days.\n\nAdd your syllabus in **☰ → My Syllabus**, then create exams in "
                "**Study Hub → Exams & Planner**, and ask me again.")
    lines, first = ["### 📅 Upcoming exams - next 30 days"], None
    for e in ex:
        done, total = progress(e)
        lines.append(f"\n**{e['name']}** · {subj_label(e)} · {_fdate(e['date'])} {_hm(e['time'])} · **{days_left(e)} days left** · "
                     f"{done}/{total} chapters done · finish all by **{_fdate((date.fromisoformat(e['date']) - timedelta(days=1)).isoformat())}**")
        cur = None
        for c in e["chapters"]:
            if _csub(e, c) != cur:
                cur = _csub(e, c)
                lines.append(f"\n*{cur}*")
            if c["done"]:
                lines.append(f"- ✅ {c['name']}")
            else:
                first = first or (e, c)
                lines.append(f"- ⬜ {c['name']} · [▶️ videos]({yt_url(e['cls'], _csub(e, c), c['name'], e['level'])})")
    if first:
        lines.append(f"\n👉 **Start with:** {_csub(*first)} - **{first[1]['name']}** (earliest deadline). "
                     "Say **make a time table** and I'll schedule every chapter day by day.")
    return "\n".join(lines)


def _first_dates(plan):
    out = {}
    for ds in sorted(plan["days"]):
        for it in plan["days"][ds]:
            if it.get("ci") is not None and it["text"].startswith("📖"):
                out.setdefault((it["exam_id"], it["ci"]), ds)
    return out


def make_timetable_reply(user):
    exams = [e for e in get_exams(user) if days_left(e) >= 0]
    if not exams:
        return ("I need at least one upcoming exam first. Add your syllabus in **☰ → My Syllabus**, create the exam in "
                "**Study Hub → Exams & Planner**, then say *make a time table* again.")
    plan = build_plan(user)
    first = _first_dates(plan)
    lines = ["### 🗓️ Your study time table is ready",
             f"Built from **{len(exams)} exam(s)** and your daily routine - every chapter is scheduled to finish **at least 1 day before its exam**, "
             "as early as possible. Reminders are ON (alerts + voice; email if enabled)."]
    if plan.get("boosted"):
        lines.append("⚡ I added an early-morning study block so everything fits.")
    for e in sorted(exams, key=lambda e: e["date"]):
        lines.append(f"\n**{e['name']} · {subj_label(e)}** ({_fdate(e['date'])})")
        for i, c in enumerate(e["chapters"]):
            when = "" if c["done"] else (f" → {_fdate(first[(e['id'], i)])}" if (e["id"], i) in first else "")
            lines.append(f"- {'✅' if c['done'] else '📖'} {_csub(e, c)}: {c['name']}{when}")
    lines.append("\n**Next 7 days**")
    for ds in sorted(plan["days"])[:7]:
        its = [i for i in plan["days"][ds] if i["kind"] in ("study", "exam")]
        lines.append(f"\n**{_fdate(ds)}**")
        lines += [f"- {_hm(i['t'])} {i['text']}{_link(i)}" for i in its] or ["- rest day 🎉"]
    if plan["late"]:
        lines.append("\n⚠️ **Not enough study time for:** " + ", ".join(plan["late"][:6]) + " - add study blocks or move an exam date.")
    lines.append("\nSee everything: **Study Hub → Exams & Planner → Full Plan** or **☰ → Time Table → Study Planner**.")
    return "\n".join(lines)


def exam_digest_text(user):
    ex = upcoming(user, 30)
    if not ex:
        return None
    out = [f"Good morning {user}! Your exam digest for {date.today():%A %d %B}.", ""]
    for e in ex:
        done, total = progress(e)
        pend = [f"{_csub(e, c)}: {c['name']}" for c in e["chapters"] if not c["done"]]
        out.append(f"* {e['name']} ({subj_label(e)}) - {_fdate(e['date'])} {_hm(e['time'])} - {days_left(e)} days left - {done}/{total} chapters done")
        if pend:
            out.append("   Still to study: " + ", ".join(pend[:8]) + ("..." if len(pend) > 8 else ""))
    items = [i for i in day_items(user) if i["kind"] in ("study", "exam")]
    if items:
        out += ["", "Today's study plan:"] + [f"  {_hm(i['t'])} - {_strip_emoji(i['text'])}" for i in items]
    return "\n".join(out + ["", "You've got this! - Jarvis"])


def context_for_llm(user):
    ex = upcoming(user, 30)
    if not ex:
        return ""
    return "; ".join(f"{subj_label(e)} {e['name']} on {e['date']} ({days_left(e)}d, {progress(e)[0]}/{progress(e)[1]} done, pending: "
                     f"{', '.join(c['name'] for c in e['chapters'] if not c['done'])[:160]})" for e in ex[:4])[:900]


NEXT_RE = re.compile(r"\b(what (should i|do i|to) study|study next|what'?s next to study|upcoming exams?|my exams?)\b", re.I)
TT_RE = re.compile(r"\b(make|create|build|generate|prepare|set up)\b.{0,25}\b(time\s?table|timetable|study plan|study schedule)\b", re.I)


def handle_study_command(user, text):
    if TT_RE.search(text):
        return make_timetable_reply(user)
    if NEXT_RE.search(text):
        return next_to_study_text(user)
    return None


# ----------------------------- UI -----------------------------
def _goto_syllabus():
    st.session_state.mode = "Syllabus"


def _paper_prompt(e, chapters, key):
    pattern = ""
    if int(e["marks"]) == 80:
        pattern = "Use EXACTLY this structure (total 80 marks):\n" + "\n".join(
            f"- Section {s}: {n} - {q} = {m} marks" for s, n, q, m in PAPER_80) + "\n"
    return (f"Create a MEDIUM-difficulty written test paper for CBSE-style Class {e['cls']} ({subj_label(e)}), exam level: {e['level']}. "
            f"Total marks: {e['marks']}, time: 3 hours.\nCover ONLY these chapters (nothing outside them): {'; '.join(chapters)}.\n{pattern}"
            "Include general instructions, marks beside every question, internal choice in long-answer questions, balanced chapter coverage "
            "and a difficulty mix of roughly 50% easy / 40% medium / 10% hard. Do not copy real board papers verbatim. Use markdown. "
            + ("After the paper add 'ANSWER KEY & MARKING SCHEME' (concise)." if key else ""))


def _tab_add_exam(user):
    subs = syl.subjects(user)
    if not subs:
        st.info("📖 Your syllabus is empty. Exams use **only** chapters you saved in My Syllabus.")
        st.button("📖 Open My Syllabus", on_click=_goto_syllabus, type="primary")
        return
    c1, c2 = st.columns(2)
    name = c1.text_input("Exam name", "Half-Yearly Exam", key="ex_name")
    level = c2.selectbox("Exam level", LEVELS, index=1, key="ex_level")
    c3, c4, c5 = st.columns(3)
    d = c3.date_input("Exam date", date.today() + timedelta(days=14), key="ex_date")
    t = c4.time_input("Exam time", datetime.strptime("09:00", "%H:%M").time(), key="ex_time")
    marks = c5.number_input("Total marks", 10, 100, 80, key="ex_marks")
    chosen = st.multiselect("Subjects in this exam (you can pick several)", subs, default=subs[:1], key="ex_subs")
    selected, total = {}, 0
    for sub in chosen:
        chs = syl.chapters_of(user, sub)
        selected[sub] = st.multiselect(f"{sub} - chapters", chs, default=chs, key=f"ex_ch_{sub}_{len(chs)}")
        total += len(selected[sub])
    st.caption(f"{total} chapter(s) from {len(chosen)} subject(s) - only from your syllabus.")
    if total and d <= date.today() + timedelta(days=1):
        st.warning("The exam is within a day - chapters can't finish a day before it.")
    if st.button("➕ Add exam", type="primary", disabled=not (name and total)):
        cls = syl.info(user, chosen[0]).get("cls", "10")
        add_exam(user, {"name": name, "subject": ", ".join(chosen), "subjects": chosen, "cls": cls, "level": level,
                        "book": "", "date": d.isoformat(), "time": t.strftime("%H:%M"), "marks": int(marks),
                        "chapters": [{"name": c, "subject": s, "done": False} for s in chosen for c in selected[s]]})
        st.success(f"Added '{name}' with {total} chapters.")
        st.rerun()


def _tab_exams(user, client, model):
    exams = sorted(get_exams(user), key=lambda e: (e["date"], e["time"]))
    if not exams:
        st.info("No exams yet - add one in the **➕ Add Exam** tab.")
        return
    nxt = [e for e in exams if days_left(e) >= 0]
    if nxt:
        done, total = progress(nxt[0])
        a, b, c = st.columns(3)
        a.metric("Next exam", nxt[0]["name"], f"{days_left(nxt[0])} days left", delta_color="off")
        b.metric("Chapters done", f"{done}/{total}")
        c.metric("Exams ahead", len(nxt))
    for e in exams:
        left, (done, total) = days_left(e), progress(e)
        dot = "⚫" if left < 0 else "🔴" if left <= 7 else "🟡" if left <= 14 else "🟢"
        tag = "finished" if left < 0 else f"{left} days left"
        with st.expander(f"{dot} {e['name']} · {subj_label(e)} · {_fdate(e['date'])} {_hm(e['time'])} · {tag} · {done}/{total} ✔"):
            st.progress(done / total if total else 0.0, text=f"{done} completed · {total - done} not completed")
            st.caption(f"Class {e['cls']} · {e['level']} · {e['marks']} marks · finish every chapter by "
                       f"{_fdate((date.fromisoformat(e['date']) - timedelta(days=1)).isoformat())}")
            cur = None
            for i, c in enumerate(e["chapters"]):
                if _csub(e, c) != cur:
                    cur = _csub(e, c)
                    st.markdown(f"**{cur}**")
                a, b = st.columns([8, 1])
                new = a.checkbox(c["name"], value=c["done"], key=f"ch_{e['id']}_{i}")
                b.markdown(f"[▶️]({yt_url(e['cls'], cur, c['name'], e['level'])})", help="Search YouTube")
                if new != c["done"]:
                    set_chapter(user, e["id"], i, new)
                    st.rerun()
            have = {(c["subject"], c["name"]) for c in e["chapters"]}
            more = [(s, c) for s, c in syl.pairs(user) if (s, c) not in have]
            if more:
                x, y = st.columns([5, 1])
                pick = x.selectbox("Add a chapter from my syllabus", more, format_func=lambda p: f"{p[0]} - {p[1]}", key=f"nc_{e['id']}",
                                   label_visibility="collapsed")
                if y.button("➕", key=f"ncb_{e['id']}"):
                    add_chapter(user, e["id"], pick[0], pick[1])
                    st.rerun()
            with st.popover("📺 Find best videos for a chapter"):
                opts = [(_csub(e, c), c["name"]) for c in e["chapters"]]
                ch = st.selectbox("Chapter", opts, format_func=lambda p: f"{p[0]} - {p[1]}", key=f"vc_{e['id']}")
                if st.button("Search", key=f"vs_{e['id']}"):
                    vids = find_videos(e["cls"], ch[0], ch[1], e["level"])
                    for v in vids:
                        st.markdown(f"- [{v['title']}]({v['url']})")
                    if not vids:
                        st.markdown(f"[Open YouTube search]({yt_url(e['cls'], ch[0], ch[1], e['level'])})")
                st.markdown(f"📚 [NCERT textbooks]({NCERT_LINK})")
            st.markdown("**📝 Practice paper**")
            scope = st.radio("Chapters to cover", ["Completed chapters", "All chapters"], horizontal=True, key=f"sc_{e['id']}")
            key_on = st.toggle("Include answer key", value=True, key=f"ak_{e['id']}")
            chs = [f"{_csub(e, c)}: {c['name']}" for c in e["chapters"] if c["done"] or scope == "All chapters"]
            if st.button("Generate medium paper", key=f"gp_{e['id']}", disabled=not chs, type="primary"):
                with st.spinner("Jarvis is setting your paper..."):
                    try:
                        st.session_state[f"paper_{e['id']}"] = su.ask(client, model, _paper_prompt(e, chs, key_on), temperature=0.4)
                    except Exception as err:
                        st.error(str(err))
            if st.session_state.get(f"paper_{e['id']}"):
                paper = st.session_state[f"paper_{e['id']}"]
                st.markdown(paper)
                p1, p2 = st.columns(2)
                p1.download_button("⬇️ .md", paper.encode(), f"{e['name']}_paper.md", key=f"pd_{e['id']}", use_container_width=True)
                if p2.button("📄 Build PDF", key=f"pp_{e['id']}", use_container_width=True):
                    from image_generation_and_pdf import build_pdf
                    st.session_state[f"paperpdf_{e['id']}"] = build_pdf(f"{e['name']} - Practice Paper", paper)
                if st.session_state.get(f"paperpdf_{e['id']}"):
                    st.download_button("⬇️ Download PDF", st.session_state[f"paperpdf_{e['id']}"], f"{e['name']}_paper.pdf",
                                       "application/pdf", key=f"pdd_{e['id']}")
            if st.button("🗑 Delete this exam", key=f"de_{e['id']}"):
                delete_exam(user, e["id"])
                st.rerun()


def _save_routine(user, new):
    d = su.load(user)
    d["routine"] = new
    su.save(user, d)
    if d.get("plan"):
        build_plan(user)


def _tab_routine(user):
    R = _routine(user)
    st.caption("Tell Jarvis your day. He fits study blocks around it - and **emails/alerts you at every time below** "
               "(turn on email in Control Panel → Alerts).")
    fields = [("wake", "⏰ Wake up"), ("breakfast", "🍳 Breakfast"), ("school_start", "🏫 School starts"), ("school_end", "🚌 School ends"),
              ("home", "🏠 Back home"), ("study1_start", "📖 Study 1 start"), ("study1_end", "📖 Study 1 end"),
              ("free_start", "🎮 Free time start"), ("free_end", "🎮 Free time end"), ("study2_start", "📖 Study 2 start"),
              ("study2_end", "📖 Study 2 end"), ("dinner", "🍽️ Dinner"), ("rev_start", "🧠 Revision start"),
              ("rev_end", "🧠 Revision end"), ("sleep", "😴 Sleep")]
    new, cols = dict(R), st.columns(3)
    for i, (k, label) in enumerate(fields):
        new[k] = cols[i % 3].time_input(label, datetime.strptime(R[k], "%H:%M").time(), key=f"rt_{k}").strftime("%H:%M")
    c1, c2 = st.columns(2)
    if c1.button("💾 Save routine", use_container_width=True):
        _save_routine(user, new)
        st.success("Routine saved.")
    if c2.button("⚙️ Generate / refresh my study plan", type="primary", use_container_width=True):
        _save_routine(user, new)
        st.session_state.plan_msg = build_plan(user)

    st.markdown("##### ➕ Extra daily reminders")
    st.caption("e.g. **12:00 AM** Time to sleep · **7:00 AM** Wake up · **8:45 PM** Time for dinner")
    for i, x in enumerate(R.get("extras", [])):
        a, b, c = st.columns([2, 5, 1])
        a.markdown(f"**{_hm(x['t'])}**")
        b.markdown(f"{x['text']} · _{x['days']}_")
        if c.button("🗑", key=f"xr_{i}"):
            ex = [y for j, y in enumerate(R["extras"]) if j != i]
            _save_routine(user, {**R, "extras": ex})
            st.rerun()
    with st.form("extra_form", clear_on_submit=True):
        f1, f2, f3 = st.columns([2, 4, 2])
        tt = f1.time_input("Time", datetime.strptime("00:00", "%H:%M").time())
        tx = f2.text_input("What should Jarvis tell you?", placeholder="Time to sleep")
        dy = f3.selectbox("Repeat", DAY_OPTS)
        if st.form_submit_button("➕ Add reminder", use_container_width=True) and tx.strip():
            _save_routine(user, {**R, "extras": R.get("extras", []) + [{"t": tt.strftime("%H:%M"), "text": tx.strip(), "days": dy}]})
            st.rerun()
    plan = st.session_state.get("plan_msg")
    if plan:
        study = sum(1 for v in plan["days"].values() for i in v if i["kind"] == "study")
        st.success(f"Plan ready: {len(plan['days'])} days, {study} study blocks." + (" ⚡ Early-morning block added." if plan.get("boosted") else ""))
        if plan["late"]:
            st.warning("Not enough time for: " + ", ".join(plan["late"][:8]))


def render_full_plan(user):
    """Everything you must do to complete your upcoming exams - deadlines + day-by-day table."""
    plan = su.load(user).get("plan")
    exams = [e for e in get_exams(user) if days_left(e) >= 0]
    if not exams:
        st.info("No upcoming exams. Add your syllabus, then an exam in **Study Hub → Exams & Planner**.")
        return
    if not plan or not plan.get("days"):
        st.info("No plan yet.")
        if st.button("⚙️ Build my plan now", type="primary"):
            build_plan(user)
            st.rerun()
        return
    first = _first_dates(plan)
    st.markdown("#### 🎯 Deadlines")
    for e in sorted(exams, key=lambda e: e["date"]):
        done, total = progress(e)
        dl = (date.fromisoformat(e["date"]) - timedelta(days=1)).isoformat()
        sched = [first[(e["id"], i)] for i, c in enumerate(e["chapters"]) if (e["id"], i) in first]
        st.markdown(f"**{e['name']}** · {subj_label(e)} · exam {_fdate(e['date'])} {_hm(e['time'])} · **finish by {_fdate(dl)}**"
                    + (f" · last chapter planned {_fdate(max(sched))}" if sched else " · all chapters done 🎉"))
        st.progress(done / total if total else 1.0, text=f"{done}/{total} chapters completed")
    if plan.get("boosted"):
        st.info("⚡ An early-morning study block was added automatically so every chapter finishes before its exam.")
    if plan["late"]:
        st.warning("⚠️ Cannot fit: " + ", ".join(plan["late"][:8]) + ". Move an exam date or add study time.")
    st.markdown("#### 🗓️ Day-by-day plan")
    f1, f2 = st.columns([3, 2])
    which = f1.selectbox("Show", ["All exams"] + [e["name"] for e in exams], key="fp_exam")
    only_study = f2.toggle("Study blocks only", value=True, key="fp_only")
    rows = []
    for ds in sorted(plan["days"]):
        for it in plan["days"][ds]:
            if only_study and it["kind"] not in ("study", "exam"):
                continue
            if which != "All exams" and it.get("exam") != which and it["kind"] in ("study", "exam"):
                continue
            rows.append({"Date": _fdate(ds), "Time": _hm(it["t"]) + (f"-{_hm(it['end'])}" if it.get("end") else ""),
                         "Subject": it.get("subject", ""), "Task": _strip_emoji(it["text"]), "Exam": it.get("exam", "")})
    st.dataframe(rows, hide_index=True, use_container_width=True, height=min(520, 40 + 36 * max(len(rows), 1)))
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Download plan (CSV)", buf.getvalue().encode(), "study_plan.csv", "text/csv", use_container_width=True)
    if c2.button("🔄 Rebuild plan", use_container_width=True):
        build_plan(user)
        st.rerun()


def render_exam_planner(user, client, model):
    st.caption(f"💾 Saved automatically: `{su.user_dir(user)}exams.json` + `exams.txt` · plan: `study_plan.json` · routine: `daily_routine.json`")
    t1, t2, t3, t4 = st.tabs(["📋 My Exams", "➕ Add Exam", "🗓️ Routine & Daily Schedule", "🗺️ Full Plan"])
    with t1:
        _tab_exams(user, client, model)
    with t2:
        _tab_add_exam(user)
    with t3:
        _tab_routine(user)
    with t4:
        render_full_plan(user)


def render_my_day(user):
    plan = su.load(user).get("plan")
    now = now_ist()
    cur, shown_next = now.hour * 60 + now.minute, False
    if not plan or not plan.get("days"):
        st.info("No exam plan yet - showing your daily routine. Add exams, then say **make a time table** in chat.")
    else:
        st.caption(f"Plan generated {plan['generated'].replace('T', ' ')} · updates automatically when you tick chapters.")
    lines = []
    for it in day_items(user):
        past = _mins(it["t"]) < cur
        mark = "✔️" if past else ("▶️ **NEXT**" if not shown_next else "•")
        shown_next = shown_next or not past
        end = f"–{_hm(it['end'])}" if it.get("end") else ""
        lines.append(f"{mark} **{_hm(it['t'])}{end}** {it['text']}{_link(it)}")
    st.markdown("\n\n".join(lines) or "Nothing scheduled today.")
    exams_by_id, shown = {e["id"]: e for e in get_exams(user)}, False
    st.markdown("**✅ Tick off what you finished**")
    for it in day_items(user):
        e = exams_by_id.get(it.get("exam_id"))
        if it.get("ci") is None or not it["text"].startswith("📖") or not e or e["chapters"][it["ci"]]["done"]:
            continue
        shown = True
        if st.button(f"✅ Done: {it['subject']} - {it['chapter']}", key=f"md_{it['exam_id']}_{it['ci']}"):
            mins = max(15, _mins(it["end"]) - _mins(it["t"])) if it.get("end") else 60
            su.log_study(user, mins, it["subject"])          # counts toward your streak
            set_chapter(user, it["exam_id"], it["ci"], True)  # and the plan re-builds itself
            st.rerun()
    if not shown:
        st.caption("Nothing to tick off right now.")
    if st.button("🔄 Rebuild plan"):
        build_plan(user)
        st.rerun()
