from flask import Flask, request, redirect, render_template
from database import (
    init_db, add_mix, get_all_mixes, get_mix_by_id,
    add_track_to_mix, get_tracks_for_mix,
    get_mix_track_row, update_mix_track,
    get_mix_cover, update_mix_cover, update_mix_links,
    delete_mix_track, delete_mix,
    search_tracks, search_mixes,
    get_all_tags, set_mix_tags, get_mix_tags, update_mix_tags,
    get_all_tags_with_counts, delete_tags
)
from utils import (slugify, highlight, _normalize_time, _strip_brackets_tail)
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



@app.route("/", methods=["GET"])
def home():
    q = request.args.get("q", "").strip()

    track_results = []
    mix_results = []

    if q:
        raw_tracks = search_tracks(q)
        for mix_id, mix_title, cover, mix_track_id, artist, title, sc, time_value in raw_tracks:
            track_label = title if not artist else f"{artist} — {title}"
            if time_value:
                track_label = f"[{time_value}] {track_label}"

            track_results.append({
                "mix_id": mix_id,
                "mix_title_html": highlight(mix_title, q),
                "track_label_html": highlight(track_label, q)
            })

        raw_mixes = search_mixes(q)
        for mix_id, title, youtube, soundcloud, cover in raw_mixes:
            mix_results.append({
                "mix_id": mix_id,
                "title_html": highlight(title, q),
                "cover": cover
            })

    return render_template("home.html", q=q, track_results=track_results, mix_results=mix_results)

@app.route("/mixes")
def mixes_page():
    raw_mixes = get_all_mixes()

    mixes = []
    for m in raw_mixes:
        mix_id, title, youtube, soundcloud, cover, tags = m
        mixes.append({
            "id": mix_id,
            "title": title,
            "cover": cover,
            "tags": tags
        })

    return render_template("mixes.html", mixes=mixes)


@app.route("/add-mix", methods=["GET", "POST"])

def add_mix_page():
    error_msg = ""
    if request.method == "GET" and request.args.get("err") == "too_large":
        error_msg = "❌ Файл завеликий (максимум 3MB)."
    title_value = ""
    youtube_value = ""
    soundcloud_value = ""
    tags_value = ""

    if request.method == "POST":
        title_value = request.form.get("title", "")
        youtube_value = request.form.get("youtube", "")
        soundcloud_value = request.form.get("soundcloud", "")
        tags_value = request.form.get("tags", "")
        # нормалізація тегів (comma-style)
        raw_tags = request.form.get("tags", "")
        tags_list = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
        tags_value = ", ".join(tags_list)

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
                add_mix(title_value.strip(), youtube_value.strip(), soundcloud_value.strip(), cover_path, tags_value.strip())
                return redirect("/mixes")

    return render_template("add_mix.html",
                           error_msg=error_msg,
                           title_value=title_value,
                           youtube_value=youtube_value,
                           soundcloud_value=soundcloud_value,
                           tags_value=tags_value)

@app.route("/mix/<int:mix_id>", methods=["GET", "POST"])
def mix_detail(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return "<h2>Мікс не знайдено</h2><p><a href='/mixes'>Назад</a></p>"

    track_error_msg = ""

    # помилки обкладинки
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

    # додавання треку
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

    tracks_raw = get_tracks_for_mix(mix_id)

    # розпаковка міксу
    mix_id_db, mix_title, youtube, sc_mix, cover, _tags_cache = mix

    tags_list = get_mix_tags(mix_id_db)  # тільки список
    tags_input = ", ".join(tags_list)  # рядок для input

    # підготуємо треки для шаблону як dict-об’єкти
    tracks = []
    for mix_track_id, artist, title, sc_track, time_value in tracks_raw:
        tracks.append({
            "mix_track_id": mix_track_id,
            "artist": artist,
            "title": title,
            "sc_track": sc_track,
            "time_value": time_value
        })

    return render_template(
        "mix_detail.html",
        mix_id=mix_id_db,
        mix_title=mix_title,
        youtube=youtube,
        sc_mix=sc_mix,
        cover=cover,
        cover_error_msg=cover_error_msg,
        track_error_msg=track_error_msg,
        tracks=tracks,
        tags=tags_list,          # для плашок
        tags_input=tags_input  # для <input value="...">
    )

@app.route("/tags", methods=["GET"])
def tags_page():
    rows = get_all_tags_with_counts()
    tags = [{"id": r[0], "name": r[1], "cnt": r[2]} for r in rows]
    return render_template("tags.html", tags=tags)

@app.route("/tags/delete", methods=["POST"])
def delete_tags_page():
    raw_ids = request.form.getlist("tag_id")
    tag_ids = []
    for x in raw_ids:
        try:
            tag_ids.append(int(x))
        except ValueError:
            pass

    if tag_ids:
        delete_tags(tag_ids)

    return redirect("/tags")

@app.route("/mix/<int:mix_id>/import-tracks", methods=["POST"])
def import_tracks(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return redirect("/mixes")

    text = request.form.get("bulk", "").strip()
    if not text:
        return redirect(f"/mix/{mix_id}")

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for line in lines:
        # ---- 0) пропускаємо службові рядки ----
        low = line.lower()
        if "://" in low:
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
        title = title.strip()
        artist = artist.strip()
        soundcloud = soundcloud.strip()
        time_value = time_value.strip()

        if not title:
            continue

        ok = add_track_to_mix(mix_id, artist, title, soundcloud, time_value)

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

@app.route("/mix/<int:mix_id>/update-track/<int:mix_track_id>", methods=["POST"])
def update_track_inline(mix_id, mix_track_id):
    artist = request.form.get("artist", "")
    title = request.form.get("title", "")
    soundcloud = request.form.get("soundcloud", "")
    time_value = request.form.get("time", "")

    ok = update_mix_track(mix_track_id, artist, title, soundcloud, time_value)
    if not ok:
        return redirect(f"/mix/{mix_id}?err=track_title_required")

    return redirect(f"/mix/{mix_id}")


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
    mix_id_db, mix_title, youtube, soundcloud, cover, tags = mix

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

@app.route("/mix/<int:mix_id>/update-tags", methods=["POST"])
def update_tags(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return redirect("/mixes")

    raw_tags = request.form.get("tags", "").strip()

    # ✅ захист від випадків коли в поле потрапили [] або ['tag'] (щоб не плодити сміття)
    if raw_tags in ("[]", ""):
        tags_list = []
    else:
        # якщо раптом залишилось щось типу "['rally house']" — прибираємо дужки по краях
        raw_tags = raw_tags.strip().strip("[]")
        raw_tags = raw_tags.replace("'", "").replace('"', "")
        tags_list = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]

    tags_value = ", ".join(tags_list)

    set_mix_tags(mix_id, tags_list)  # ✅ якщо set_mix_tags очікує список
    update_mix_tags(mix_id, tags_value)  # ✅ кеш-рядок
    return redirect(f"/mix/{mix_id}")

@app.route("/mix/<int:mix_id>/update-links", methods=["POST"])
def update_mix_links_inline(mix_id):
    youtube = request.form.get("youtube", "")
    sc_mix = request.form.get("soundcloud", "")

    update_mix_links(mix_id, youtube, sc_mix)
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
def delete_mix_page(mix_id):
    delete_mix(mix_id)
    return redirect("/mixes")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)