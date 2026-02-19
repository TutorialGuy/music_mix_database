from flask import Flask, request, redirect, render_template
from database import (
    init_db, add_mix, get_all_mixes, get_mix_by_id,
    add_track_to_mix, get_tracks_for_mix,
    get_mix_track_row, update_mix_track,
    get_mix_cover, update_mix_cover,
    delete_mix_track, delete_mix,
    search_tracks
)
import os
from werkzeug.utils import secure_filename
from PIL import Image
import re

app = Flask(__name__)

# Має бути перевірка на 3 MB, але треба пропустити хоч щось, щоб зберегти поля
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

# Тека для збереження обкладинок (краще синхронізувати через хмару разом з БД)
COVERS_FOLDER = os.path.join(app.root_path, "static", "covers")
os.makedirs(COVERS_FOLDER, exist_ok=True)

ALLOWED_EXT = {"jpg", "jpeg", "png", "bmp", "webp", "gif"}

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)   # прибрати спецсимволи
    text = re.sub(r"\s+", "-", text)      # пробіли -> "-"
    return text.strip("-")

@app.route("/", methods=["GET"])
def home():
    q = request.args.get("q", "").strip()
    results = []

    if q:
        raw = search_tracks(q)

        # Підготуємо дані для шаблону
        for mix_id, mix_title, cover, mix_track_id, artist, title, sc, time_value in raw:
            track_label = title if not artist else f"{artist} — {title}"
            if time_value:
                track_label = f"[{time_value}] {track_label}"

            results.append({
                "mix_id": mix_id,
                "mix_title": mix_title,
                "track_label": track_label
            })

    return render_template("home.html", q=q, results=results)

@app.route("/mixes")
def mixes_page():
    mixes = get_all_mixes()
    html = "<h2>Список міксів</h2>"
    html += '<p><a href="/add-mix">Додати мікс</a> | <a href="/">На головну</a></p>'

    if not mixes:
        html += "<p>Поки що немає міксів.</p>"
    else:
        html += "<ul style='list-style:none;padding-left:0;'>"

        for mix_id, title, youtube, soundcloud, cover in mixes:
            cover_html = ""
            if cover:
                cover_url = "/" + cover.replace("\\", "/")
                cover_html = f"""
                <img src="{cover_url}" alt="cover"
                     style="width:64px;height:64px;object-fit:cover;border:1px solid #ccc;border-radius:8px;margin-right:10px;">
                """

            html += f"""
            <li style="display:flex;align-items:center;margin:8px 0;">
                {cover_html}
                <a href="/mix/{mix_id}">{title}</a>
                <form method="post" action="/delete-mix/{mix_id}" style="display:inline;margin-left:12px;"
                      onsubmit="return confirm('Ви впевнені, що бажаєте це зробити?');">
                    <button type="submit" style="color:red;">Видалити</button>
                </form>
            </li>
            """

        html += "</ul>"

    return html

@app.route("/add-mix", methods=["GET", "POST"])

def add_mix_page():
    error_msg = ""
    if request.method == "GET" and request.args.get("err") == "too_large":
        error_msg = "❌ Файл завеликий (максимум 3MB)."
    title_value = ""
    youtube_value = ""
    soundcloud_value = ""

    if request.method == "POST":
        title_value = request.form.get("title", "")
        youtube_value = request.form.get("youtube", "")
        soundcloud_value = request.form.get("soundcloud", "")

        cover_path = None
        file = request.files.get("cover")

        # 1) Назва обов'язкова
        if not title_value.strip():
            error_msg = "❌ Назва міксу — обов'язкова."
            # одразу показуємо форму з помилкою
            # (нижче HTML уже використає title_value/youtube_value/soundcloud_value)
        else:
            # 2) Якщо файл обраний — перевіряємо його
            if file and file.filename:
                filename = secure_filename(file.filename)
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

                if ext not in ALLOWED_EXT:
                    error_msg = "❌ Непідтримуваний формат (jpeg/png/bmp/webp/gif)."
                else:
                    # 2.1) Перевірка об'єму (3MB)
                    file.stream.seek(0, os.SEEK_END)
                    size_bytes = file.stream.tell()
                    file.stream.seek(0)

                    if size_bytes > 3 * 1024 * 1024:
                        error_msg = "❌ Файл завеликий (максимум 3MB)."
                    else:
                        # 2.2) Перевірка пікселів (3000×3000)
                        try:
                            img = Image.open(file.stream)
                            w, h = img.size
                            file.stream.seek(0)
                            if w > 3000 or h > 3000:
                                error_msg = "❌ Зображення занадто велике (максимум 3000×3000)."
                        except (OSError, ValueError):
                            error_msg = "❌ Неможливо прочитати зображення. Спробуй інший файл."

                # 2.3) Зберігаємо файл тільки якщо немає помилок
                if not error_msg:
                    import time

                    safe_title = slugify(title_value.strip()) or "mix"
                    timestamp = int(time.time())

                    unique_name = f"{safe_title}_cover_{timestamp}.{ext}"

                    save_to = os.path.join(COVERS_FOLDER, unique_name)
                    file.save(save_to)

                    cover_path = f"static/covers/{unique_name}"

            # 3) Додаємо мікс тільки якщо немає помилок (включно з картинкою)
            if not error_msg:
                add_mix(title_value.strip(), youtube_value.strip(), soundcloud_value.strip(), cover_path)
                return redirect("/mixes")

    html = "<h2>Додати мікс</h2>"

    if error_msg:
        html += f'<p style="color:red;"><b>{error_msg}</b></p>'

    html += f"""
    <form method="post" enctype="multipart/form-data">
        <p>Обкладинка:<br>
    <input type="file" name="cover" accept="image/*"><br>
    <small style="display:block;color:gray;margin-top:4px;">
    Формати: JPG/JPEG, PNG, BMP, WEBP, GIF • Макс: 3MB • До 3000×3000px 
</small>

</p>

        <p>Назва міксу (*):<br>
           <input name="title" value="{title_value}" style="width:400px"></p>

        <p>YouTube:<br>
           <input name="youtube" value="{youtube_value}" style="width:400px"></p>

        <p>SoundCloud:<br>
           <input name="soundcloud" value="{soundcloud_value}" style="width:400px"></p>

        <button type="submit">Зберегти</button>
    </form>
    <p><a href="/">На головну</a></p>
    """
    return html


@app.route("/mix/<int:mix_id>", methods=["GET", "POST"])
def mix_detail(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return "<h2>Мікс не знайдено</h2><p><a href='/mixes'>Назад</a></p>"

    track_error_msg = ""

    # ---- помилки обкладинки (тільки новий механізм) ----
    cover_error_msg = ""
    cover_err = request.args.get("cover_err", "")
    if cover_err == "format":
        cover_error_msg = "❌ Непідтримуваний формат обкладинки (jpeg/png/bmp/webp/gif)."
    elif cover_err == "size":
        cover_error_msg = "❌ Файл обкладинки завеликий (максимум 3MB)."
    elif cover_err == "pixels":
        cover_error_msg = "❌ Зображення обкладинки занадто велике (максимум 3000×3000)."
    elif cover_err == "bad":
        cover_error_msg = "❌ Не вдалося прочитати зображення. Спробуй інший файл."

    # ---- додавання треку ----
    if request.method == "POST":
        artist = request.form.get("artist", "")
        title = request.form.get("title", "")
        time_value = request.form.get("time", "")
        sc_track = request.form.get("soundcloud", "")

        ok = add_track_to_mix(mix_id, artist, title, sc_track, time_value)

        if ok:
            return redirect(f"/mix/{mix_id}")
        else:
            track_error_msg = "❌ Введіть хоча б назву треку (поле обов'язкове)."

    tracks = get_tracks_for_mix(mix_id)

    # важливо: тут soundcloud — це soundcloud МІКСУ, не треку
    mix_id, mix_title, youtube, sc_mix, cover = mix

    html = f'<div id="top"></div><h2>Мікс: {mix_title}</h2>'
    html += """
    <p style="margin-top:6px;">
      <a href="/" style="margin-right:12px;">🏠 На головну</a>
      <a href="/mixes">⬅️ Назад до списку міксів</a>
    </p>
    """

    # --- Двоколонковий блок: зліва трекліст, справа обкладинка ---
    html += """
    <div style="display:flex; gap:20px; align-items:flex-start; margin-top:10px;">
      <div style="flex: 2; min-width: 420px;">
    """

    # ---- трекліст ----
    html += "<h3>Трекліст</h3>"
    if not tracks:
        html += "<p>Поки що немає треків.</p>"
    else:
        html += "<ol>"
        for mix_track_id, artist, title, sc_track, time_value in tracks:
            label = title if not artist else f"{artist} — {title}"
            if time_value:
                label = f"[{time_value}] {label}"
            if sc_track:
                label += f' (<a href="{sc_track}" target="_blank">SoundCloud</a>)'
            label += f' <a href="/edit-track/{mix_track_id}">[редагувати]</a>'
            label += f' <a href="/delete-track/{mix_track_id}" style="color:red;">[видалити]</a>'
            html += f"<li>{label}</li>"
        html += "</ol>"

    html += """
      </div>
      <div style="flex: 1; min-width: 260px;">
    """

    # прев'ю обкладинки (праворуч)
    if cover:
        cover_url = "/" + cover.replace("\\", "/")
        html += f"""
        <div style="margin-bottom:10px;">
            <img src="{cover_url}" alt="cover"
                 style="width:260px; height:260px; object-fit:cover; border:1px solid #ccc; border-radius:10px;">
        </div>
        """

    html += "<h3 style='margin-top:0;'>Обкладинка</h3>"

    if cover_error_msg:
        html += f'<p style="color:red;"><b>{cover_error_msg}</b></p>'

    html += f"""
    <form method="post" action="/mix/{mix_id}/update-cover" enctype="multipart/form-data">
        <input type="file" name="cover" accept="image/*"><br>
        <small style="display:block;color:gray;margin-top:4px;">
            Формати: JPG/JPEG, PNG, BMP, WEBP, GIF<br>
            Макс: 3MB • До 3000×3000
        </small>
        <button type="submit" style="margin-top:8px;">Оновити</button>
    </form>
    """

    # ---- посилання міксу ----
    html += "<hr style='margin:15px 0;'>"
    html += "<h3 style='margin-top:0;'>Посилання</h3>"
    html += "<p>"
    if youtube:
        html += f'YouTube: <a href="{youtube}" target="_blank">{youtube}</a><br>'
    if sc_mix:
        html += f'SoundCloud: <a href="{sc_mix}" target="_blank">{sc_mix}</a><br>'
    html += "</p>"

    html += """
      </div>
    </div>
    """

    # ---- помилка додавання треку ----
    if track_error_msg:
        html += f'<p style="color:red;"><b>{track_error_msg}</b></p>'

    # ---- форма додавання треку ----
    html += """
    <h3>Імпорт трекліста (з тексту)</h3>
    <form method="post" action="/mix/{mix_id}/import-tracks">
        <textarea name="bulk"
          placeholder="Встав сюди трекліст (кожен трек з нового рядка)

    Підтримуються формати:
    • 00:04:32 Artist - Track
    • 04:32 Artist - Track
    • Artist - Track
    • Track"
          style="width:700px;height:220px;padding:10px;font-family:monospace;"></textarea>

        <button type="submit">Імпортувати</button>
    </form>
    """.replace("{mix_id}", str(mix_id))

    html += """
    <h3>Додати трек</h3>
    <form method="post">
        <p>Таймкод (ГГ:ХХ:СС):<br>
        <input name="time" placeholder="00:00:00" style="width:150px"></p>

        <p>Артист:<br>
        <input name="artist" style="width:300px"></p>

        <p>Назва треку:<br>
        <input name="title" style="width:300px"></p>

        <p>SoundCloud:<br>
        <input name="soundcloud" style="width:400px"></p>

        <button type="submit">Додати</button>
    </form>
    """

    html += """
    <p style="margin-top:20px;">
      <a href="/" style="margin-right:12px;">🏠 На головну</a>
      <a href="/mixes">⬅️ Назад до списку міксів</a>
    </p>
    """
    html += """
    <a href="#top"
       title="Вгору"
       style="
         position:fixed;
         right:18px;
         bottom:18px;
         background:#f2f2f2;
         border:1px solid #ccc;
         border-radius:12px;
         padding:10px 12px;
         text-decoration:none;
         color:#000;
         box-shadow:0 2px 6px rgba(0,0,0,0.15);
       ">⬆️</a>

    <style>
      html { scroll-behavior: smooth; }
    </style>
    """

    return html

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
    return re.sub(r"\s*\[[^\]]+\]\s*$", "", s).strip()


@app.route("/mix/<int:mix_id>/import-tracks", methods=["POST"])
def import_tracks(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return redirect("/mixes")

    text = request.form.get("bulk", "").strip()
    if not text:
        return redirect(f"/mix/{mix_id}")

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    added = 0

    for line in lines:
        # ---- 0) пропускаємо службові рядки ----
        low = line.lower()
        if low.startswith("http://") or low.startswith("https://"):
            continue
        if low.startswith("disc "):
            continue
        if "tracklist" in low and low.endswith(":"):
            continue

        # прибираємо хвіст [..] якщо є
        line = _strip_brackets_tail(line)

        artist = ""
        title = ""
        time_value = ""
        soundcloud = ""

        # ---- 1) Формат A: TIME - TITLE ----
        # 0:04:50 - Lighthouse Suite
        m = re.match(r"^(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*-\s*(.+)$", line)
        if m:
            time_value = _normalize_time(m.group(1))
            title = m.group(2).strip()

        else:
            # ---- 2) Формат B: N. TITLE TIME ----
            # 1. Sine Mora - High Score (Results) 0:00
            m = re.match(r"^\d+\.\s*(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$", line)
            if m:
                title_part = m.group(1).strip()
                time_value = _normalize_time(m.group(2))
                # title_part може бути "Artist - Title"
                if " - " in title_part:
                    artist, title = [p.strip() for p in title_part.split(" - ", 1)]
                elif " — " in title_part:
                    artist, title = [p.strip() for p in title_part.split(" — ", 1)]
                else:
                    title = title_part
            else:
                # ---- 3) Формат C: N. TITLE ----
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
                else:
                    # ---- 4) Формат D: TIME Artist - Title (без дефісу між часом і рештою) ----
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
                    else:
                        # ---- 5) Просто текст ----
                        title = line.strip()

        # мінімальна валідація
        if not title:
            continue

        ok = add_track_to_mix(mix_id, artist, title, soundcloud, time_value)
        if ok:
            added += 1

    return redirect(f"/mix/{mix_id}")

@app.route("/edit-track/<int:mix_track_id>", methods=["GET", "POST"])
def edit_track(mix_track_id):
    row = get_mix_track_row(mix_track_id)
    if not row:
        return "<h2>Запис не знайдено</h2><p><a href='/mixes'>Назад</a></p>"

    mix_track_id, mix_id, artist, title, soundcloud, time_value, pos = row

    error_msg = ""

    # Значення для форми (GET)
    form_artist = artist or ""
    form_title = title or ""
    form_soundcloud = soundcloud or ""
    form_time = time_value or ""

    if request.method == "POST":
        # Значення для форми (POST)
        form_artist = request.form.get("artist", "")
        form_title = request.form.get("title", "")
        form_soundcloud = request.form.get("soundcloud", "")
        form_time = request.form.get("time", "")

        ok = update_mix_track(mix_track_id, form_artist, form_title, form_soundcloud, form_time)
        if ok:
            return redirect(f"/mix/{mix_id}")
        error_msg = "❌ Назва треку обов'язкова."

    html = "<h2>Редагувати трек у цьому міксі</h2>"
    html += f'<p><a href="/mix/{mix_id}">Назад до міксу</a> | <a href="/">На головну</a></p>'

    if error_msg:
        html += f'<p style="color:red;"><b>{error_msg}</b></p>'

    html += f"""
    <form method="post">
        <p>Артист (не обов'язково):<br>
           <input name="artist" value="{form_artist}" style="width:300px"></p>

        <p>Назва треку (обов'язково):<br>
           <input name="title" value="{form_title}" style="width:300px"></p>

        <p>SoundCloud (не обов'язково):<br>
           <input name="soundcloud" value="{form_soundcloud}" style="width:400px"></p>

        <p>Час у міксі (не обов'язково):<br>
           <input name="time" value="{form_time}" placeholder="00:00:00" style="width:150px"></p>

        <button type="submit">Зберегти</button>
    </form>
    """

    html += f'<p><a href="/mix/{mix_id}">Назад до міксу</a> | <a href="/">На головну</a></p>'
    return html

@app.route("/mix/<int:mix_id>/update-cover", methods=["POST"])
def update_cover(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return redirect("/mixes")

    file = request.files.get("cover")
    if not file or not file.filename:
        return redirect(f"/mix/{mix_id}")  # нічого не вибрали

    # 1) перевіряємо розширення
    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        return redirect(f"/mix/{mix_id}?cover_err=format")

    # 2) перевірка об’єму 3MB (ручна)
    file.stream.seek(0, os.SEEK_END)
    size_bytes = file.stream.tell()
    file.stream.seek(0)
    if size_bytes > 3 * 1024 * 1024:
        return redirect(f"/mix/{mix_id}?cover_err=size")

    # 3) перевірка пікселів
    try:
        img = Image.open(file.stream)
        w, h = img.size
        file.stream.seek(0)
        if w > 3000 or h > 3000:
            return redirect(f"/mix/{mix_id}?cover_err=pixels")
    except (OSError, ValueError):
        return redirect(f"/mix/{mix_id}?cover_err=bad")

    # 4) зберігаємо новий файл з назвою від назви міксу
    import time
    mix_id_db, mix_title, youtube, soundcloud, cover = mix

    safe_title = slugify(mix_title) or f"mix_{mix_id}"
    timestamp = int(time.time())

    new_name = f"{safe_title}_cover_{timestamp}.{ext}"
    save_to = os.path.join(COVERS_FOLDER, new_name)
    file.save(save_to)

    new_cover_path = f"static/covers/{new_name}"

    # 5) оновлюємо БД + видаляємо старий файл
    old_cover = get_mix_cover(mix_id)
    update_mix_cover(mix_id, new_cover_path)

    if old_cover and old_cover != new_cover_path:
        old_full = os.path.join(os.getcwd(), old_cover)
        if os.path.exists(old_full):
            try:
                os.remove(old_full)
            except OSError:
                pass

    return redirect(f"/mix/{mix_id}")

@app.route("/delete-track/<int:mix_track_id>")
def delete_track(mix_track_id):
    row = get_mix_track_row(mix_track_id)
    if not row:
        return redirect("/")

    mix_track_id, mix_id, artist, title, soundcloud, time_value, pos = row

    delete_mix_track(mix_track_id)

    return redirect(f"/mix/{mix_id}")

@app.route("/delete-mix/<int:mix_id>", methods=["POST"])
def delete_mix_route(mix_id):
    delete_mix(mix_id)
    return redirect("/mixes")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)