from flask import Flask, request, redirect, render_template, send_from_directory, jsonify, Response
from database import (
    init_db, add_mix, get_all_mixes, get_mix_by_id,
    add_track_to_mix, get_tracks_for_mix,
    get_mix_track_row, update_mix_track,
    get_mix_cover, update_mix_cover, update_mix_links,
    delete_mix_track, delete_mix,
    search_tracks, search_mixes,
    set_mix_tags, get_mix_tags, update_mix_tags,
    get_all_tags_with_counts, delete_tags,
    delete_mix_tracks_bulk, save_track_order,
    update_mix_duration, get_all_mixes_sorted
)
from utils import (slugify, highlight, _normalize_time, _strip_brackets_tail, time_to_seconds,
                   parse_track_line, parse_tags_input, parse_duration_to_seconds, format_seconds_to_hms, normalize_url)
import os
from werkzeug.utils import secure_filename
from PIL import Image


app = Flask(__name__)

# Має бути перевірка на 3 MB, але треба пропустити хоч щось, щоб зберегти поля
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

# Тека для збереження обкладинок
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COVERS_FOLDER = os.path.join(BASE_DIR, "covers")
os.makedirs(COVERS_FOLDER, exist_ok=True)

ALLOWED_EXT = {"jpg", "jpeg", "png", "bmp", "webp", "gif"}

app.jinja_env.filters["time_to_seconds"] = time_to_seconds
app.jinja_env.globals["format_seconds_to_hms"] = format_seconds_to_hms


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
    sort = request.args.get("sort", "added")
    direction = request.args.get("dir", "desc")

    raw_mixes = get_all_mixes_sorted(sort, direction)

    mixes = []
    for m in raw_mixes:
        mix_id, title, youtube, soundcloud, cover, tags, duration_sec = m
        mixes.append({
            "id": mix_id,
            "title": title,
            "cover": cover,
            "tags": tags,
            "duration_sec": duration_sec
        })

    return render_template(
        "mixes.html",
        mixes=mixes,
        current_sort=sort,
        current_dir=direction
    )

@app.route("/add-mix", methods=["GET", "POST"])
def add_mix_page():
    error_msg = ""

    title_value = ""
    youtube_value = ""
    soundcloud_value = ""
    spotify_value = ""
    tags_value = ""
    duration_value = ""
    duration_sec = None

    if request.method == "POST":
        # --- debug (можеш потім прибрати) ---
        print("DEBUG form keys:", list(request.form.keys()))
        print("DEBUG files keys:", list(request.files.keys()))

        # --- поля ---
        title_value = request.form.get("title", "").strip()
        youtube_value = request.form.get("youtube", "").strip()
        soundcloud_value = request.form.get("soundcloud", "").strip()
        spotify_value = request.form.get("spotify", "").strip()

        # нормалізація URL
        youtube_value = normalize_url(youtube_value)
        soundcloud_value = normalize_url(soundcloud_value)
        spotify_value = normalize_url(spotify_value)

        raw_tags = request.form.get("tags", "").strip()
        tags_list = parse_tags_input(raw_tags)          # ✅ список
        tags_value = ", ".join(tags_list)               # ✅ щоб лишалось у полі

        duration_value = request.form.get("duration", "").strip()
        duration_sec = parse_duration_to_seconds(duration_value)
        if duration_value and duration_sec is None:
            error_msg = "❌ Тривалість має бути у форматі MM:SS або HH:MM:SS."

        # --- валідація назви ---
        if not title_value:
            error_msg = "❌ Назва міксу — обов'язкова."

        # --- обкладинка ---
        cover_path = None
        file = request.files.get("cover")

        if not error_msg and file and file.filename:
            filename = secure_filename(file.filename)
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

            if ext not in ALLOWED_EXT:
                error_msg = "❌ Непідтримуваний формат (jpeg/png/bmp/webp/gif)."
            else:
                # розмір
                file.stream.seek(0, os.SEEK_END)
                size_bytes = file.stream.tell()
                file.stream.seek(0)
                if size_bytes > 3 * 1024 * 1024:
                    error_msg = "❌ Файл завеликий (максимум 3MB)."
                else:
                    # пікселі
                    try:
                        img = Image.open(file.stream)
                        w, h = img.size
                        file.stream.seek(0)
                        if w > 3000 or h > 3000:
                            error_msg = "❌ Зображення занадто велике (максимум 3000×3000)."
                    except (OSError, ValueError):
                        error_msg = "❌ Неможливо прочитати зображення. Спробуй інший файл."

            if not error_msg:
                import time
                safe_title = slugify(title_value) or "mix"
                timestamp = int(time.time())
                new_name = f"{safe_title}_cover_{timestamp}.{ext}"

                save_to = os.path.join(COVERS_FOLDER, new_name)
                file.save(save_to)

                cover_path = f"covers/{new_name}"  # ✅ як у тебе зараз

        # --- створення мікса ---
        if not error_msg:
            new_id = add_mix(
            title_value.strip(),
            youtube_value.strip(),
            soundcloud_value.strip(),
            spotify_value.strip(),
            cover_path,
            tags_value.strip(),
            duration_sec
        )

            # ✅ зберігаємо теги у зв’язкові таблиці
            set_mix_tags(new_id, tags_list)

            return redirect("/mixes")

    all_tags = [row[1] for row in get_all_tags_with_counts()]

    return render_template(
        "add_mix.html",
        error_msg=error_msg,
        title_value=title_value,
        youtube_value=youtube_value,
        soundcloud_value=soundcloud_value,
        spotify_value=spotify_value,
        tags_value=tags_value,
        all_tags=all_tags,
        duration_value=duration_value
    )

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
    mix_id_db, mix_title, youtube, sc_mix, spotify, cover, _tags_cache, duration_sec = mix

    tags_list = get_mix_tags(mix_id_db)  # тільки список
    tags_input = ", ".join(tags_list)  # рядок для input
    duration_value = format_seconds_to_hms(duration_sec)

    # підготуємо треки для шаблону як dict-об’єкти
    tracks = []
    for mix_track_id, artist, title, sc_track, time_value in tracks_raw:
        yt_at = None

        if youtube and time_value:
            sec = time_to_seconds(time_value)
            if sec > 0:
                joiner = "&" if "?" in youtube else "?"
                yt_at = f"{youtube}{joiner}t={sec}"

        tracks.append({
            "mix_track_id": mix_track_id,
            "artist": artist,
            "title": title,
            "sc_track": sc_track,
            "time_value": time_value,
            "yt_at": yt_at
        })

    all_tags = [row[1] for row in get_all_tags_with_counts()]

    return render_template(
        "mix_detail.html",
        mix_id=mix_id_db,
        mix_title=mix_title,
        duration_sec=duration_sec,
        youtube=youtube,
        sc_mix=sc_mix,
        spotify=spotify,
        cover=cover,
        cover_error_msg=cover_error_msg,
        track_error_msg=track_error_msg,
        tracks=tracks,
        tags=tags_list,
        tags_input=tags_input,
        all_tags=all_tags
    )

@app.route("/mix/<int:mix_id>/update-duration", methods=["POST"])
def update_duration(mix_id):
    raw = request.form.get("duration", "")
    sec = parse_duration_to_seconds(raw)
    if raw.strip() and sec is None:
        return redirect(f"/mix/{mix_id}?err=bad_duration")
    update_mix_duration(mix_id, sec)
    return redirect(f"/mix/{mix_id}")

@app.route("/covers/<path:filename>")
def covers_file(filename):
    return send_from_directory(COVERS_FOLDER, filename)

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

    added = 0
    for line in lines:
        parsed = parse_track_line(line)
        if not parsed:
            continue

        artist, title, soundcloud, time_value = parsed

        ok = add_track_to_mix(mix_id, artist, title, soundcloud, time_value)
        if ok:
            added += 1

    return redirect(f"/mix/{mix_id}")

@app.route("/mix/<int:mix_id>/delete-tracks", methods=["POST"])
def delete_tracks_bulk(mix_id):
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])

    # базова валідація
    if not isinstance(ids, list):
        return jsonify({"ok": False}), 400

    # перетворити в int, відсіяти сміття
    clean_ids = []
    for x in ids:
        try:
            clean_ids.append(int(x))
        except (TypeError, ValueError):
            pass

    if not clean_ids:
        return jsonify({"ok": True, "deleted": 0})

    deleted = delete_mix_tracks_bulk(mix_id, clean_ids)
    return jsonify({"ok": True, "deleted": deleted})

@app.route("/mix/<int:mix_id>/update-track/<int:mix_track_id>", methods=["POST"])
def update_track_inline(mix_id, mix_track_id):
    artist = request.form.get("artist", "")
    title = request.form.get("title", "")
    soundcloud = request.form.get("soundcloud", "")
    time_value = request.form.get("time", "")

    ok = update_mix_track(mix_track_id, artist, title, soundcloud, time_value)
    if not ok:
        return jsonify({"ok": False}), 400

    return jsonify({
        "ok": True,
        "artist": artist.strip(),
        "title": title.strip(),
        "time": time_value.strip(),
        "soundcloud": soundcloud.strip()
    })

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
    mix_id_db = mix[0]
    mix_title = mix[1]
    old_cover_path = mix[4]  # якщо треба

    safe_title = slugify(mix_title) or f"mix_{mix_id}"
    timestamp = int(time.time())

    new_name = f"{safe_title}_cover_{timestamp}.{ext}"
    save_to = os.path.join(COVERS_FOLDER, new_name)
    file.save(save_to)

    new_cover_path = f"covers/{new_name}"

    # 5) оновлюємо БД + видаляємо старий файл
    old_cover = get_mix_cover(mix_id)
    update_mix_cover(mix_id, new_cover_path)

    if old_cover and old_cover != new_cover_path:
        old_full = os.path.join(os.getcwd(), old_cover.replace("/", os.sep))
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

    raw_tags = request.form.get("tags", "")
    tags_list = parse_tags_input(raw_tags)

    set_mix_tags(mix_id, tags_list)

    return redirect(f"/mix/{mix_id}")

@app.route("/mix/<int:mix_id>/update-links", methods=["POST"])
def update_mix_links_inline(mix_id):
    youtube = request.form.get("youtube", "").strip()
    sc_mix = request.form.get("soundcloud", "").strip()
    spotify = request.form.get("spotify", "").strip()

    youtube = normalize_url(youtube)
    sc_mix = normalize_url(sc_mix)
    spotify = normalize_url(spotify)

    update_mix_links(mix_id, youtube, sc_mix, spotify)
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

from flask import jsonify

@app.route("/mix/<int:mix_id>/reorder-tracks", methods=["POST"])
def reorder_tracks(mix_id):
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"ok": False}), 400

    ids_int = []
    for x in ids:
        try:
            ids_int.append(int(x))
        except (TypeError, ValueError):
            pass

    save_track_order(mix_id, ids_int)
    return jsonify({"ok": True})

@app.route("/mix/<int:mix_id>/export-tracklist")
def export_tracklist(mix_id: int):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return redirect("/mixes")

    mix_id_db, mix_title, youtube, sc_mix, cover, _tags_cache, duration_sec = mix

    tracks_raw = get_tracks_for_mix(mix_id_db)

    lines = []
    lines.append(f"TITLE: {mix_title}")

    if youtube:
        lines.append(f"YOUTUBE: {youtube}")
    if sc_mix:
        lines.append(f"SOUNDCLOUD: {sc_mix}")
    if duration_sec:
        lines.append(f"DURATION: {format_seconds_to_hms(duration_sec)}")

    lines.append("")  # порожній рядок
    lines.append("TRACKLIST:")

    for mix_track_id, artist, title, sc_track, time_value in tracks_raw:
        artist = (artist or "").strip()
        title = (title or "").strip()
        sc_track = (sc_track or "").strip()
        time_value = (time_value or "").strip()

        # основний текст рядка
        parts = []
        if time_value:
            parts.append(time_value)

        if artist:
            parts.append(f"{artist} — {title}")
        else:
            parts.append(f"{title}")

        base = " ".join(parts)

        # SoundCloud треку (якщо є)
        if sc_track:
            base += f"  [SC: {sc_track}]"

        lines.append(base)

    content = "\n".join(lines) + "\n"
    filename = f"{slugify(mix_title) or f'mix_{mix_id_db}'}.txt"

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return Response(content, headers=headers)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)