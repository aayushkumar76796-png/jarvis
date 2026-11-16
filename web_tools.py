"""Live web access: search, page fetch, news, weather (stdlib only)."""
import html
import ipaddress
import re
import socket
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (Jarvis assistant)"}
LIVE_KEYWORDS = ("news", "latest", "today", "score", "current", "search", "price", "who won", "release date", "stock",
                 "trending", "update on", "look up", "google", "recent", "announced", "results", "notification", "sample paper",
                 "syllabus change", "exam date", "date sheet", "admit card", "cutoff", "cut off", "this year", "this week",
                 "right now", "new rule", "launched", "weather", "who is the", "when is", "how much is", "ranking")
_YEAR = re.compile(r"\b20(2[4-9]|3\d)\b")
URL_RE = re.compile(r"https?://[^\s<>\"')]+")


def needs_live_data(text):
    low = (text or "").lower()
    return any(k in low for k in LIVE_KEYWORDS) or bool(_YEAR.search(low))


def should_search(text, mode="Smart"):
    """Off = never, Smart = time-sensitive / factual-looking questions, Always = every real question."""
    if mode == "Off" or not text or text.startswith("/"):
        return False
    if mode == "Always":
        return len(text.split()) >= 3
    return needs_live_data(text)


def extract_urls(text):
    return URL_RE.findall(text or "")[:2]


def _get(url, timeout=6, limit=600_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        return r.read(limit).decode("utf-8", errors="ignore"), ctype


def search_web(query, max_results=4):
    """DuckDuckGo HTML search -> list of {title, url, snippet}."""
    try:
        page, _ = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query))
    except Exception:
        return []
    out = []
    blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
    for href, title, snip in blocks[:max_results]:
        if "uddg=" in href:
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        out.append({"title": strip(title), "url": href, "snippet": strip(snip)})
    return out


def format_search_results(results):
    if not results:
        return "No live search results available."
    return "\n".join(f"- {r['title']} ({r['url']}): {r['snippet']}" for r in results)


def _is_public_host(host):
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def fetch_page_text(url, max_chars=5000):
    """Readable text of a public web page. Blocks localhost/private networks."""
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname or not _is_public_host(p.hostname):
        return "Blocked: only public http(s) pages can be fetched."
    try:
        page, ctype = _get(url, timeout=8)
    except Exception as e:
        return f"Could not fetch page: {e}"
    if "html" not in ctype and "text" not in ctype:
        return f"Unsupported content type: {ctype}"
    page = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", page)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text).strip()
    head = f"Title: {html.unescape(title.group(1)).strip()}\n" if title else ""
    return head + text[:max_chars]


def get_news(topic="", count=5):
    """Headlines from Google News RSS (India edition)."""
    q = urllib.parse.quote(topic) if topic else ""
    url = (f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en" if topic
           else "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en")
    try:
        xml, _ = _get(url)
        items = ET.fromstring(xml).findall(".//item")[:count]
        return [{"title": i.findtext("title", ""), "url": i.findtext("link", ""),
                 "date": i.findtext("pubDate", "")} for i in items]
    except Exception:
        return []


def format_news(items):
    return "\n".join(f"- {n['title']} ({n['date'][:16]})" for n in items) or "No headlines available."


_WMO = {0: ("☀️", "Clear"), 1: ("🌤️", "Mostly clear"), 2: ("⛅", "Partly cloudy"), 3: ("☁️", "Overcast"),
        45: ("🌫️", "Fog"), 48: ("🌫️", "Fog"), 51: ("🌦️", "Light drizzle"), 53: ("🌦️", "Drizzle"), 55: ("🌧️", "Heavy drizzle"),
        61: ("🌧️", "Light rain"), 63: ("🌧️", "Rain"), 65: ("🌧️", "Heavy rain"), 71: ("🌨️", "Snow"), 80: ("🌦️", "Showers"),
        81: ("🌧️", "Showers"), 82: ("⛈️", "Violent showers"), 95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm"), 99: ("⛈️", "Thunderstorm")}


def _wmo(code):
    return _WMO.get(code, ("🌡️", "Unknown"))


def get_weather_data(city="Bengaluru"):
    """Open-Meteo (free, no key). Returns dict with 'ok', 'short', current values and a 3-day forecast."""
    import json
    from datetime import datetime
    try:
        geo = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(city), timeout=6)[0])
        g = geo["results"][0]
        url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=4"
               "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"
               "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max") % (g["latitude"], g["longitude"])
        d = json.loads(_get(url, timeout=6)[0])
        c, dl = d["current"], d["daily"]
        ico, desc = _wmo(c["weather_code"])
        days = []
        for i in range(1, 4):
            di, _ = _wmo(dl["weather_code"][i])
            days.append({"day": datetime.fromisoformat(dl["time"][i]).strftime("%a"), "icon": di,
                         "hi": round(dl["temperature_2m_max"][i]), "lo": round(dl["temperature_2m_min"][i]),
                         "rain": dl["precipitation_probability_max"][i]})
        return {"ok": True, "city": g["name"], "icon": ico, "desc": desc, "temp": round(c["temperature_2m"]),
                "feels": round(c["apparent_temperature"]), "humidity": c["relative_humidity_2m"],
                "wind": round(c["wind_speed_10m"]), "days": days,
                "short": f"{ico} {round(c['temperature_2m'])}°C {desc}"}
    except Exception:
        return {"ok": False, "city": city, "short": "Weather offline"}


def get_weather(city="Bengaluru"):
    return get_weather_data(city)["short"]
