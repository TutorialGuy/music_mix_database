import re
from markupsafe import escape, Markup
from typing import Optional
import json
import ast

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)   # прибрати спецсимволи
    text = re.sub(r"\s+", "-", text)      # пробіли -> "-"
    return text.strip("-")

def highlight(text: str, query: str) -> Markup:
    if not text:
        return Markup("")
    if not query:
        return Markup(escape(text))

    safe_text = str(escape(text))
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    highlighted = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", safe_text)
    return Markup(highlighted)

def parse_tags_input(raw: str) -> list[str]:
    """
    Приймає теги з форми (комами), але також вміє 'врятувати'
    випадки, коли туди потрапив рядок виду:
      "['game','jazz']" або '["game","jazz"]'
    Повертає чистий список тегів без лапок/дужок.
    """
    if not raw:
        return []

    s = raw.strip()

    # 1) Якщо це схоже на JSON-масив: ["a","b"]
    if s.startswith("[") and s.endswith("]"):
        # пробуємо JSON
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # пробуємо Python repr: ['a','b']
        try:
            data = ast.literal_eval(s)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except (ValueError, SyntaxError):
            pass

        # якщо не вдалося — падатимемо до split нижче

    # 2) Основний режим: комами
    parts = [p.strip() for p in s.split(",")]

    cleaned = []
    for p in parts:
        if not p:
            continue
        # знімаємо зайві лапки/дужки по краях
        # p = p.strip().strip("[](){}")
        p = p.strip().strip("'").strip('"')
        p = p.strip()
        if p:
            cleaned.append(p)

    # прибрати дублікати з збереженням порядку
    seen = set()
    out = []
    for t in cleaned:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t.lower())
    return out

def _normalize_time(t: str) -> str:
    """Приводимо 0:00 / 12:34 / 1:02:03 до HH:MM:SS"""
    t = t.strip()
    parts = t.split(":")
    if len(parts) == 2:   # MM:SS
        mm, ss = parts
        return f"00:{int(mm):02d}:{int(ss):02d}"
    if len(parts) == 3:   # H:MM:SS або HH:MM:SS
        hh, mm, ss = parts
        return f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d}"
    return ""

def _strip_brackets_tail(s: str) -> str:
    """Відрізаємо хвіст типу [8m 21s] або [14m]"""
    return re.sub(r"\s*\[[^]]+]\s*$", "", s).strip()

def parse_track_line(line: str) -> Optional[tuple[str, str, str, str]]:
    """
    Повертає (artist, title, soundcloud, time_value) або None якщо рядок треба пропустити.
    Підтримує кілька форматів треклістів.
    """

    if not line:
        return None

    low = line.lower().strip()

    # 0) пропускаємо службові рядки
    if "://" in low:
        return None
    if low.startswith("disc "):
        return None
    if "tracklist" in low and low.endswith(":"):
        return None

    # прибираємо хвіст типу [8m 21s]
    line = _strip_brackets_tail(line.strip())

    artist = ""
    title = ""
    time_value = ""
    soundcloud = ""  # поки не парсимо з тексту

    # A) TIME - TITLE
    # 0:04:50 - Lighthouse Suite
    m = re.match(r"^(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*-\s*(.+)$", line)
    if m:
        time_value = _normalize_time(m.group(1))
        title = m.group(2).strip()
        return (artist, title, soundcloud, time_value)

    # B) N. TITLE TIME
    # 1. Sine Mora - High Score (Results) 0:00
    m = re.match(r"^\d+\.\s*(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$", line)
    if m:
        title_part = m.group(1).strip()
        time_value = _normalize_time(m.group(2))
        if " - " in title_part:
            artist, title = [p.strip() for p in title_part.split(" - ", 1)]
        elif " — " in title_part:
            artist, title = [p.strip() for p in title_part.split(" — ", 1)]
        else:
            title = title_part
        if title:
            return (artist, title, soundcloud, time_value)
        return None

    # C) N. TITLE
    # 1. Aural Imbalance - Realm of Innocence (1999)
    m = re.match(r"^\d+\.\s*(.+)$", line)
    if m:
        title_part = m.group(1).strip()
        if " - " in title_part:
            artist, title = [p.strip() for p in title_part.split(" - ", 1)]
        elif " — " in title_part:
            artist, title = [p.strip() for p in title_part.split(" — ", 1)]
        else:
            title = title_part
        if title:
            return (artist, title, soundcloud, time_value)
        return None

    # D) TIME Artist - Title (без дефісу між часом і рештою)
    # 00:00 Kudos - Horizontal Movements
    m = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", line)
    if m:
        time_value = _normalize_time(m.group(1))
        rest = m.group(2).strip()
        if " - " in rest:
            artist, title = [p.strip() for p in rest.split(" - ", 1)]
        elif " — " in rest:
            artist, title = [p.strip() for p in rest.split(" — ", 1)]
        else:
            title = rest
        if title:
            return (artist, title, soundcloud, time_value)
        return None

    # E) Просто текст — може бути "Artist - Title" або просто "Title"
    text = line.strip()
    if not text:
        return None
    if " - " in text:
        artist, title = [p.strip() for p in text.split(" - ", 1)]
    elif " — " in text:
        artist, title = [p.strip() for p in text.split(" — ", 1)]
    else:
        title = text
    return (artist, title, soundcloud, time_value)

def time_to_seconds(t: str) -> int:
    """
    Приймає "HH:MM:SS" або "MM:SS" або "H:MM:SS".
    Повертає секунди. Якщо формат невірний — 0.
    """
    if not t:
        return 0

    t = t.strip()
    parts = t.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0

    if len(nums) == 2:      # MM:SS
        mm, ss = nums
        return mm * 60 + ss
    if len(nums) == 3:      # HH:MM:SS
        hh, mm, ss = nums
        return hh * 3600 + mm * 60 + ss

    return 0

def parse_duration_to_seconds(raw: str) -> int | None:
    """
    Приймає:
      "SS"
      "MM:SS"
      "HH:MM:SS"
    Повертає секунди або None якщо порожньо/невалідно.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    if not re.fullmatch(r"\d+(:\d{1,2}){0,2}", s):
        return None

    parts = [int(p) for p in s.split(":")]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        mm, ss = parts
        return mm * 60 + ss
    hh, mm, ss = parts
    return hh * 3600 + mm * 60 + ss


def format_seconds_to_hms(seconds: int | None) -> str:
    if seconds is None:
        return ""
    if seconds < 0:
        return ""
    hh = seconds // 3600
    mm = (seconds % 3600) // 60
    ss = seconds % 60
    if hh > 0:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return f"{mm:02d}:{ss:02d}"

def normalize_url(url: str) -> str:
    """
    Якщо url порожній -> повертає "".
    Якщо немає http:// або https:// -> додає https://
    """
    if not url:
        return ""
    s = str(url).strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return s
    return "https://" + s