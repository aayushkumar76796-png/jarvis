"""Jarvis 'agent' brain: before answering, a planner step decides which tools to use (web, page reader, calculator,
your syllabus / exams / notes / chats, weather, time), gathers evidence, and the normal answer is then written from it."""
import ast
import json
import math
import operator
import re
from datetime import datetime

import study_utils as su
from web_tools import fetch_page_text, format_search_results, get_weather, search_web

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow,
        ast.Mod: operator.mod, ast.USub: operator.neg, ast.FloorDiv: operator.floordiv}
_FUNCS = {"sqrt": math.sqrt, "sin": lambda x: math.sin(math.radians(x)), "cos": lambda x: math.cos(math.radians(x)),
          "tan": lambda x: math.tan(math.radians(x)), "log": math.log10, "ln": math.log, "abs": abs, "round": round}
_CONST = {"pi": math.pi, "e": math.e}

TOOL_HELP = """Tools (call at most one per step):
- web_search: live internet search. input = search query
- fetch_page: read a web page. input = full URL
- calc: exact maths (trig in DEGREES, sqrt, log, pi). input = expression like 2*sqrt(9)+sin(30)
- syllabus: the student's saved chapters. input = subject name or empty
- exams: upcoming exams and pending chapters. input = empty
- notes: search the student's notes, flashcards, tasks and chats. input = keywords
- weather: input = city
- time: current date and time. input = empty"""


def safe_calc(expr):
    """Evaluates arithmetic only (no names/attributes/calls except the allow-list)."""
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Name) and n.id in _CONST:
            return _CONST[n.id]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and len(n.args) == 1:
            return _FUNCS[n.func.id](ev(n.args[0]))
        raise ValueError("unsupported expression")
    v = ev(ast.parse(expr.replace("^", "**").replace("×", "*").replace("÷", "/"), mode="eval").body)
    return round(v, 10) if isinstance(v, float) else v


def run_tool(name, arg, user, city="Bengaluru"):
    """-> (observation text, [source dicts])"""
    arg = (arg or "").strip()
    try:
        if name == "web_search":
            res = search_web(arg, 4)
            return format_search_results(res), res
        if name == "fetch_page":
            return fetch_page_text(arg, 2500), []
        if name == "calc":
            return f"{arg} = {safe_calc(arg)}", []
        if name == "syllabus":
            import syllabus_utils as syl
            subs = [arg] if arg in syl.subjects(user) else syl.subjects(user)
            return "\n".join(f"{s}: " + ", ".join(syl.chapters_of(user, s)) for s in subs) or "No syllabus saved yet.", []
        if name == "exams":
            import exam_utils
            return exam_utils.context_for_llm(user) or "No upcoming exams.", []
        if name == "notes":
            import data_utils
            hits = data_utils.search_all(user, arg)[:6]
            return "\n".join(f"[{h['Type']}] {h['Where']}: {h['Match']}" for h in hits) or "Nothing found.", []
        if name == "weather":
            return get_weather(arg or city), []
        if name == "time":
            return datetime.now().strftime("%A %d %B %Y, %I:%M %p"), []
    except Exception as e:
        return f"(tool error: {e})", []
    return "(unknown tool)", []


def wants_agent(text, mode="Auto"):
    if mode == "Off" or not text or text.startswith("/"):
        return False
    words = text.split()
    if mode == "Always":
        return len(words) >= 3
    low = text.lower()
    return len(words) >= 6 and (text.rstrip().endswith("?") or re.match(r"(why|how|what|when|who|which|explain|compare|calculate|solve|find|tell me|give me|suggest|plan)\b", low) is not None
                                or bool(re.search(r"\d", low)))


def _json(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0)) if m else {}


def gather(client, model, user, question, on_step=None, max_steps=3, city="Bengaluru"):
    """Planner loop. Returns (context_text, sources, steps[(tool, input, observation)])."""
    steps, srcs, ctx = [], [], ""
    for _ in range(max_steps):
        seen = "\n".join(f"- {t}({a}) -> {o[:500]}" for t, a, o in steps) or "(nothing yet)"
        try:
            r = client.chat.completions.create(model=model, temperature=0, messages=[
                {"role": "system", "content": "You are the planning brain of Jarvis, a study assistant. Decide whether tools are needed to answer the "
                 "student's message accurately. " + TOOL_HELP + "\nReply with ONLY JSON: {\"tool\": \"name\", \"input\": \"...\"} to use a tool, "
                 "or {\"done\": true} when you have enough or no tool is needed. Prefer calc for any arithmetic, web_search for anything recent or "
                 "uncertain, syllabus/exams/notes for questions about the student's own study data. Never repeat a tool call."},
                {"role": "user", "content": f"Student message: {question}\n\nEvidence so far:\n{seen}"}])
            d = _json(r.choices[0].message.content or "")
        except Exception:
            break
        tool, arg = d.get("tool"), str(d.get("input", ""))
        if d.get("done") or tool not in ("web_search", "fetch_page", "calc", "syllabus", "exams", "notes", "weather", "time"):
            break
        if any(t == tool and a == arg for t, a, _o in steps):
            break
        if on_step:
            on_step(tool, arg)
        obs, res = run_tool(tool, arg, user, city)
        steps.append((tool, arg, obs))
        srcs += res
    if steps:
        ctx = "[Tool results gathered for this question - use them, cite web results by name]\n" + "\n".join(
            f"* {t}({a}):\n{o[:1800]}" for t, a, o in steps) + "\n"
    return ctx, srcs, steps
