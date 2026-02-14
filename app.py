from flask import Flask, request, redirect
from database import (
    init_db, add_mix, get_all_mixes, get_mix_by_id,
    add_track_to_mix,
    get_tracks_for_mix,
    get_mix_track_row, update_mix_track,
    delete_mix_track
)

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Music Mix Database</h1>
    <p>Сайт працює ✅</p>
    <ul>
        <li><a href="/mixes">Список міксів</a></li>
        <li><a href="/add-mix">Додати мікс</a></li>
        <li><a href="/search">Пошук треку</a></li>
    </ul>
    """

@app.route("/add-mix", methods=["GET", "POST"])
def add_mix_page():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        youtube = request.form.get("youtube", "").strip()
        soundcloud = request.form.get("soundcloud", "").strip()

        if title:
            add_mix(title, youtube, soundcloud)

        return redirect("/mixes")

    return """
    <h2>Додати мікс</h2>
    <form method="post">
        <p>Назва міксу:<br><input name="title" style="width:400px"></p>
        <p>YouTube посилання:<br><input name="youtube" style="width:400px"></p>
        <p>SoundCloud посилання:<br><input name="soundcloud" style="width:400px"></p>
        <button type="submit">Зберегти</button>
    </form>
    <p><a href="/">Назад</a></p>
    """

@app.route("/search")
def search():
    return "<h2>Тут буде пошук треку</h2><p><a href='/'>Назад</a></p>"

@app.route("/mixes")
def mixes():
    mixes_list = get_all_mixes()

    html = "<h2>Список міксів</h2>"
    html += '<p><a href="/add-mix">➕ Додати новий мікс</a> | <a href="/">На головну</a></p>'
    html += "<ol>"

    for mix_id, title, youtube, soundcloud in mixes_list:
        html += "<li>"
        html += f'<b><a href="/mix/{mix_id}">{title}</a></b><br>'
        if youtube:
            html += f'YouTube: <a href="{youtube}" target="_blank">{youtube}</a><br>'
        if soundcloud:
            html += f'SoundCloud: <a href="{soundcloud}" target="_blank">{soundcloud}</a><br>'
        html += "</li><br>"

    html += "</ol>"
    return html

@app.route("/mix/<int:mix_id>", methods=["GET", "POST"])
def mix_detail(mix_id):
    mix = get_mix_by_id(mix_id)
    if not mix:
        return "<h2>Мікс не знайдено</h2><p><a href='/mixes'>Назад</a></p>"

    error_msg = ""

    if request.method == "POST":
        artist = request.form.get("artist", "")
        title = request.form.get("title", "")
        time_value = request.form.get("time", "")
        soundcloud = request.form.get("soundcloud", "")

        # ✅ ПРАВИЛЬНО: додаємо новий трек
        ok = add_track_to_mix(mix_id, artist, title, soundcloud, time_value)

        if ok:
            return redirect(f"/mix/{mix_id}")
        else:
            error_msg = "❌ Введіть хоча б назву треку (поле обов'язкове)."

    tracks = get_tracks_for_mix(mix_id)

    mix_id, mix_title, youtube, soundcloud = mix

    html = f"<h2>Мікс: {mix_title}</h2>"
    html += "<p>"
    if youtube:
        html += f'YouTube: <a href="{youtube}" target="_blank">{youtube}</a><br>'
    if soundcloud:
        html += f'SoundCloud: <a href="{soundcloud}" target="_blank">{soundcloud}</a><br>'
    html += "</p>"

    if error_msg:
        html += f'<p style="color:red;"><b>{error_msg}</b></p>'

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

    html += "<h3>Трекліст</h3>"

    if not tracks:
        html += "<p>Поки що немає треків.</p>"
    else:
        html += "<ol>"
        for mix_track_id, artist, title, soundcloud, time_value in tracks:
            label = title if not artist else f"{artist} — {title}"
            if time_value:
                label = f"[{time_value}] {label}"

            if soundcloud:
                label += f' (<a href="{soundcloud}" target="_blank">SoundCloud</a>)'

            label += f' <a href="/edit-track/{mix_track_id}">[редагувати]</a>'
            label += f' <a href="/delete-track/{mix_track_id}" style="color:red;">[видалити]</a>'

            html += f"<li>{label}</li>"

        html += "</ol>"

    html += "<p><a href='/mixes'>Назад до списку міксів</a></p>"
    return html

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

@app.route("/delete-track/<int:mix_track_id>")
def delete_track(mix_track_id):
    row = get_mix_track_row(mix_track_id)
    if not row:
        return redirect("/")

    mix_track_id, mix_id, artist, title, soundcloud, time_value, pos = row

    delete_mix_track(mix_track_id)

    return redirect(f"/mix/{mix_id}")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)