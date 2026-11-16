"""Jarvis's 'getting smarter every day': facts learned about you, plus a Daily Brief built from live internet data."""
import json
import re
from datetime import date

import streamlit as st

import study_utils as su
from data_paths import path as _dp
from web_tools import format_search_results, get_news, search_web

FACTS_FILE = _dp("memory_facts.json")
FEEDBACK_FILE = _dp("feedback.json")
BRIEF_FILE = _dp("daily_brief.json")
MAX_FACTS = 40


def _read(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def _write(path, data):
    json.dump(data, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ----------------------------- learned facts -----------------------------
def load_facts(user):
    return _read(FACTS_FILE).get(user, [])


def save_facts(user, facts):
    data = _read(FACTS_FILE)
    data[user] = facts[-MAX_FACTS:]
    _write(FACTS_FILE, data)


def delete_fact(user, idx):
    f = load_facts(user)
    if 0 <= idx < len(f):
        f.pop(idx)
        save_facts(user, f)


def facts_block(user):
    f = load_facts(user)
    return ("[WHAT YOU HAVE LEARNED ABOUT THIS USER - use naturally, never recite]\n" + "\n".join(f"- {x}" for x in f[-15:])[:900]) if f else ""


def learn_from_chat(client, model, user, messages):
    """Every few turns: pull durable facts (goals, weak topics, preferences) out of the recent chat."""
    recent = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in messages[-8:])
    try:
        raw = su.ask(client, model, "Extract up to 3 DURABLE facts about the student from this conversation (interests, goals, weak or strong "
                                    "topics, study preferences, exam info). Short statements. Reply with ONLY a JSON array of strings, or [] if "
                                    f"nothing durable.\n\n{recent}", temperature=0.0)
        new = [str(x).strip() for x in su.json_from(raw) if str(x).strip()]
    except Exception:
        return []
    have = {f.lower() for f in load_facts(user)}
    fresh = [f for f in new if f.lower() not in have and len(f) < 160]
    if fresh:
        save_facts(user, load_facts(user) + fresh)
    if len(load_facts(user)) > 30:
        compact_facts(client, model, user)
    return fresh


def compact_facts(client, model, user):
    """Keeps memory sharp: merges duplicates / outdated facts into at most 20."""
    try:
        raw = su.ask(client, model, "Merge these facts about a student into at most 20 short, non-duplicate statements; drop outdated ones. "
                                    "Reply with ONLY a JSON array of strings.\n" + "\n".join(f"- {f}" for f in load_facts(user)), temperature=0.0)
        merged = [str(x).strip() for x in su.json_from(raw) if str(x).strip()]
        if 3 <= len(merged) <= 30:
            save_facts(user, merged)
    except Exception:
        pass


# ----------------------------- learning from 👍 / 👎 -----------------------------
def record_feedback(user, question, answer, rating):
    data = _read(FEEDBACK_FILE)
    data.setdefault(user, []).append({"date": date.today().isoformat(), "q": question[:200], "a": answer[:400], "rating": rating})
    data[user] = data[user][-60:]
    _write(FEEDBACK_FILE, data)
    return len(data[user])


def learn_preferences(client, model, user):
    """Turns recent ratings into 'Prefers: ...' facts so answers fit you better."""
    fb = _read(FEEDBACK_FILE).get(user, [])[-12:]
    if len(fb) < 4:
        return []
    lines = "\n".join(f"{'LIKED' if f['rating'] > 0 else 'DISLIKED'} | Q: {f['q']} | A: {f['a'][:200]}" for f in fb)
    try:
        raw = su.ask(client, model, "From what this student liked and disliked, infer up to 3 answer-style preferences (length, tone, detail, examples). "
                                    "Each starts with 'Prefers' or 'Dislikes'. Reply with ONLY a JSON array of strings.\n" + lines, temperature=0.0)
        new = [str(x).strip() for x in su.json_from(raw) if str(x).strip()]
    except Exception:
        return []
    facts = [f for f in load_facts(user) if not f.startswith(("Prefers", "Dislikes"))]
    save_facts(user, facts + new)
    return new


# ----------------------------- weak topics (from quiz scores) -----------------------------
def weak_topics(user, threshold=65):
    by = {}
    for q in su.load(user)["quizzes"]:
        by.setdefault(q["topic"], []).append(100 * q["score"] / max(1, q["total"]))
    return sorted([(t, sum(v) / len(v)) for t, v in by.items() if sum(v) / len(v) < threshold], key=lambda x: x[1])


def weak_block(user):
    w = weak_topics(user)
    return ("[WEAK TOPICS from quizzes - revise these, be extra clear]\n" + "; ".join(f"{t} ({p:.0f}%)" for t, p in w[:5])) if w else ""


_WEAK_RE = re.compile(r"\b(what (should|do) i (need to )?revise|my weak (topics?|areas?|chapters?)|where am i weak|what am i weak (in|at))\b", re.I)


def handle_brain_command(user, text):
    if not _WEAK_RE.search(text):
        return None
    w = weak_topics(user)
    if not w:
        return ("🎯 No weak topics yet - take a few quizzes in **Study Hub → Quiz** and I'll track where you lose marks, "
                "then build revision around them.")
    out = ["### 🎯 Your weak topics (from quiz scores)"] + [f"- **{t}** - average {p:.0f}%" for t, p in w[:8]]
    out.append("\nSay *quiz me* to practise, or open **Study Hub → Flashcards** - missed questions are already saved as cards.")
    return "\n".join(out)


# ----------------------------- daily brief -----------------------------
def cached_brief(user):
    b = _read(BRIEF_FILE).get(user, {})
    return b.get("md", "") if b.get("date") == date.today().isoformat() else ""


def _learning_target(user):
    """The chapter Jarvis teaches you 'something new' about today: next pending exam chapter, else first syllabus chapter."""
    import exam_utils
    import syllabus_utils
    for e in exam_utils.upcoming(user, 60):
        for c in e["chapters"]:
            if not c["done"]:
                return e["cls"], c.get("subject") or e["subject"], c["name"]
    p = syllabus_utils.pairs(user)
    return ("10",) + p[0] if p else None


def daily_brief(user, client, model, force=False):
    if not force and cached_brief(user):
        return cached_brief(user)
    heads = get_news("", 5) + get_news("India education CBSE students", 3)
    head_txt = "\n".join(f"- {h['title']}" for h in heads) or "(headlines unavailable)"
    target = _learning_target(user)
    learn_ctx, learn_line = "", "pick any interesting Class 10 science or maths idea"
    if target:
        cls, subj, ch = target
        snippets = search_web(f"NCERT Class {cls} {subj} {ch} key idea explained", 3)
        learn_ctx = "\nWeb snippets for today's learning topic:\n" + format_search_results(snippets) if snippets else ""
        learn_line = f"Class {cls} {subj} - chapter '{ch}'"
    md = su.ask(client, model,
                "Write a friendly DAILY BRIEF (under 260 words, markdown) for a Class 10 student with 3 parts:\n"
                "1. **🌍 Today in the world** - 3 bullets using ONLY the headlines below (no invented news).\n"
                f"2. **💡 Learn something new today** - a 5-line explanation plus one surprising fact about: {learn_line}. Keep it accurate.\n"
                "3. **🎯 Today's challenge** - one exam-style question (answer hidden: say 'ask me for the answer').\n\n"
                f"Headlines:\n{head_txt}{learn_ctx}", temperature=0.3)
    data = _read(BRIEF_FILE)
    data[user] = {"date": date.today().isoformat(), "md": md}
    _write(BRIEF_FILE, data)
    return md


def brief_for_prompt(user):
    """Short slice of today's brief for the system prompt, so Jarvis knows fresh facts."""
    md = cached_brief(user)
    return ("[TODAY'S BRIEF - fresh info]\n" + re.sub(r"\s+", " ", md)[:600]) if md else ""
