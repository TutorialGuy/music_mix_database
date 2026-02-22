import re
from markupsafe import escape, Markup
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
        except Exception:
            pass

        # пробуємо Python repr: ['a','b']
        try:
            data = ast.literal_eval(s)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except Exception:
            pass

        # якщо не вдалося — падатимемо до split нижче

    # 2) Основний режим: комами
    parts = [p.strip() for p in s.split(",")]

    cleaned = []
    for p in parts:
        if not p:
            continue
        # знімаємо зайві лапки/дужки по краях
        p = p.strip().strip("[](){}")
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
            out.append(t)
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