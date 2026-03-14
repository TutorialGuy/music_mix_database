import sqlite3
import os

DB_NAME = "music.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS mixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            youtube TEXT,
            soundcloud TEXT,
            cover TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT,
            title TEXT NOT NULL,
            soundcloud TEXT,
            UNIQUE(artist, title)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS mix_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mix_id INTEGER NOT NULL,
            artist TEXT,
            title TEXT NOT NULL,
            soundcloud TEXT,
            time TEXT,
            pos INTEGER NOT NULL,
            FOREIGN KEY (mix_id) REFERENCES mixes(id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS mix_tags (
            mix_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (mix_id, tag_id),
            FOREIGN KEY (mix_id) REFERENCES mixes(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
        """)

        try:
            cur.execute("ALTER TABLE mixes ADD COLUMN duration_sec INTEGER")
        except sqlite3.OperationalError:
            pass

        conn.commit()

def ensure_spotify_column():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(mixes)")
        cols = {row[1] for row in cur.fetchall()}
        if "spotify" not in cols:
            cur.execute("ALTER TABLE mixes ADD COLUMN spotify TEXT")
            conn.commit()

#MIXES#
def add_mix(title: str, youtube: str, soundcloud: str, spotify: str, cover: str | None, tags: str, duration_sec: int | None = None) -> int:
    title = (title or "").strip()
    youtube_db = (youtube or "").strip() or None
    soundcloud_db = (soundcloud or "").strip() or None
    spotify_db = (spotify or "").strip() or None
    cover_db = (cover or "").strip() or None
    tags_db = (tags or "").strip() or None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mixes (title, youtube, soundcloud, spotify, cover, tags, duration_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, youtube_db, soundcloud_db, spotify_db, cover_db, tags_db, duration_sec))
        conn.commit()
        return int(cur.lastrowid)

def get_all_mixes_sorted(sort: str = "added", direction: str = "desc"):
    sort = (sort or "added").lower()
    direction = (direction or "desc").lower()
    direction_sql = "ASC" if direction == "asc" else "DESC"

    if sort == "title":
        order_sql = f"title COLLATE NOCASE {direction_sql}"
    elif sort == "duration":
        # NULL в кінець
        order_sql = f"(duration_sec IS NULL), duration_sec {direction_sql}"
    else:
        # "added" -> по id
        order_sql = f"id {direction_sql}"

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, title, youtube, soundcloud, cover, tags, duration_sec
            FROM mixes
            ORDER BY {order_sql}
        """)
        return cur.fetchall()

def get_mix_by_id(mix_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, youtube, soundcloud, spotify, cover, tags, duration_sec
            FROM mixes
            WHERE id=?
        """, (mix_id,))
        return cur.fetchone()

def get_mixes_by_tag(tag_name: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT m.id, m.title, m.cover, m.duration_sec
            FROM mixes m
            JOIN mix_tags mt ON mt.mix_id = m.id
            JOIN tags t ON t.id = mt.tag_id
            WHERE t.name = ?
            ORDER BY m.id DESC
        """, (tag_name,))
        return cur.fetchall()

def delete_mix(mix_id):
    with get_connection() as conn:
        cur = conn.cursor()

        # 1️⃣ Дізнаємось шлях до обкладинки
        cur.execute("SELECT cover FROM mixes WHERE id=?", (mix_id,))
        row = cur.fetchone()

        cover_path = row[0] if row and row[0] else None

        # 2️⃣ Видаляємо треки
        cur.execute("DELETE FROM mix_tracks WHERE mix_id=?", (mix_id,))

        # 3️⃣ Видаляємо сам мікс
        cur.execute("DELETE FROM mixes WHERE id=?", (mix_id,))

        conn.commit()

    # 4️⃣ Видаляємо файл обкладинки (після закриття з'єднання)
    if cover_path:
        # Нормалізуємо слеші
        cover_path = cover_path.replace("\\", "/")

        # якщо в БД зберігається "covers/xxx.jpg" — шлях відносно кореня проєкту
        # якщо раптом залишилось "static/covers/xxx.jpg" — теж працюватиме
        full_path = os.path.join(os.getcwd(), cover_path)

        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except OSError:
                pass

    return True

def update_mix_links(mix_id: int, youtube: str, soundcloud: str, spotify: str) -> None:
    youtube_db = (youtube or "").strip() or None
    sc_db = (soundcloud or "").strip() or None
    sp_db = (spotify or "").strip() or None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE mixes
            SET youtube=?, soundcloud=?, spotify=?
            WHERE id=?
        """, (youtube_db, sc_db, sp_db, mix_id))
        conn.commit()

def update_mix_cover(mix_id, cover_path):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE mixes SET cover=? WHERE id=?", (cover_path, mix_id))
        conn.commit()

def update_mix_duration(mix_id: int, duration_sec: int | None) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE mixes SET duration_sec=? WHERE id=?",
            (duration_sec, mix_id)
        )
        conn.commit()

#TRACKS#
def add_track_to_mix(mix_id: int, artist: str, title: str, soundcloud: str, time_value: str) -> bool:
    title = (title or "").strip()
    if not title:
        return False

    artist_db = artist.strip() if artist else None
    soundcloud_db = soundcloud.strip() if soundcloud else None
    time_db = time_value.strip() if time_value else None

    with get_connection() as conn:
        cur = conn.cursor()

        # позиція в кінці списку
        cur.execute("SELECT COALESCE(MAX(pos), 0) + 1 FROM mix_tracks WHERE mix_id=?", (mix_id,))
        pos = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO mix_tracks (mix_id, artist, title, soundcloud, time, pos)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (mix_id, artist_db, title, soundcloud_db, time_db, pos))

        conn.commit()

    return True

def get_tracks_for_mix(mix_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT id, artist, title, soundcloud, time
        FROM mix_tracks
        WHERE mix_id = ?
        ORDER BY pos
        """, (mix_id,))
        return cur.fetchall()

def update_mix_track(mix_track_id: int, artist: str, title: str, soundcloud: str, time_value: str) -> bool:
    title = (title or "").strip()
    if not title:
        return False

    artist_db = artist.strip() if artist else None
    soundcloud_db = soundcloud.strip() if soundcloud else None
    time_db = time_value.strip() if time_value else None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE mix_tracks
            SET artist=?, title=?, soundcloud=?, time=?
            WHERE id=?
        """, (artist_db, title, soundcloud_db, time_db, mix_track_id))
        conn.commit()

    return True

def delete_mix_track(mix_track_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM mix_tracks WHERE id = ?", (mix_track_id,))
        conn.commit()
    return True

def delete_mix_tracks_bulk(mix_id: int, ids: list[int]) -> int:
    if not ids:
        return 0

    with get_connection() as conn:
        cur = conn.cursor()

        # видаляємо тільки ті треки, які належать цьому міксу
        qmarks = ",".join(["?"] * len(ids))
        params = [mix_id] + ids

        cur.execute(
            f"DELETE FROM mix_tracks WHERE mix_id = ? AND id IN ({qmarks})",
            params
        )

        deleted = cur.rowcount if cur.rowcount is not None else 0

        # після видалення: “стиснути” pos щоб не було дір
        cur.execute("""
            SELECT id FROM mix_tracks
            WHERE mix_id = ?
            ORDER BY pos
        """, (mix_id,))
        rows = cur.fetchall()

        for i, (track_id,) in enumerate(rows, start=1):
            cur.execute("UPDATE mix_tracks SET pos=? WHERE id=?", (i, track_id))

        conn.commit()
        return deleted

#TAGS#
def get_mix_tags(mix_id: int) -> list[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.name
            FROM tags t
            JOIN mix_tags mt ON mt.tag_id = t.id
            WHERE mt.mix_id = ?
            ORDER BY t.name
        """, (mix_id,))
        return [r[0] for r in cur.fetchall()]

def set_mix_tags(mix_id: int, tags: list[str]) -> None:
    # 0) нормалізація + прибрати пусті
    clean = []
    seen = set()
    for t in tags:
        if t is None:
            continue
        name = str(t).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(name)

    with get_connection() as conn:
        cur = conn.cursor()

        # 1) стерти старі зв'язки
        cur.execute("DELETE FROM mix_tags WHERE mix_id=?", (mix_id,))

        # 2) додати нові
        for name in clean:
            cur.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            cur.execute("SELECT id FROM tags WHERE name=?", (name,))
            row = cur.fetchone()
            if not row:
                # якщо раптом не знайшлось — просто пропускаємо, не падаємо
                continue
            tag_id = row[0]
            cur.execute(
                "INSERT OR IGNORE INTO mix_tags (mix_id, tag_id) VALUES (?, ?)",
                (mix_id, tag_id)
            )
        conn.commit()

def get_mix_tags_with_counts(mix_id: int) -> list[tuple[str, int]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.name, COUNT(DISTINCT mt2.mix_id) as cnt
            FROM tags t
            JOIN mix_tags mt ON mt.tag_id = t.id
            LEFT JOIN mix_tags mt2 ON mt2.tag_id = t.id
            WHERE mt.mix_id = ?
            GROUP BY t.id, t.name
            ORDER BY t.name
        """, (mix_id,))
        return cur.fetchall()

def delete_tags(tag_ids: list[int]) -> None:
    if not tag_ids:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        qmarks = ",".join(["?"] * len(tag_ids))

        # спочатку прибираємо зв'язки
        cursor.execute(f"DELETE FROM mix_tags WHERE tag_id IN ({qmarks})", tag_ids)

        # потім самі теги
        cursor.execute(f"DELETE FROM tags WHERE id IN ({qmarks})", tag_ids)

        conn.commit()

def get_all_tags_with_counts():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                t.id,
                t.name,
                COUNT(DISTINCT mt.mix_id) as cnt
            FROM tags t
            LEFT JOIN mix_tags mt ON mt.tag_id = t.id
            GROUP BY t.id, t.name
            ORDER BY cnt DESC, t.name COLLATE NOCASE
        """)
        return cursor.fetchall()

def get_mix_track_row(mix_track_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, mix_id, artist, title, soundcloud, time, pos
            FROM mix_tracks
            WHERE id = ?
        """, (mix_track_id,))
        return cur.fetchone()

def get_mix_cover(mix_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT cover FROM mixes WHERE id=?", (mix_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else None

def search_tracks(query):
    q = f"%{query.strip()}%"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                m.id, m.title, m.cover,
                mt.id, mt.artist, mt.title, mt.soundcloud, mt.time
            FROM mix_tracks mt
            JOIN mixes m ON m.id = mt.mix_id
            WHERE mt.title LIKE ? OR mt.artist LIKE ?
            ORDER BY m.id DESC, mt.id ASC
        """, (q, q))
        return cur.fetchall()

def search_mixes(query):
    q = f"%{query.strip()}%"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, youtube, soundcloud, cover
            FROM mixes
            WHERE title LIKE ?
               OR youtube LIKE ?
               OR soundcloud LIKE ?
            ORDER BY id DESC
        """, (q, q, q))
        return cur.fetchall()

def save_track_order(mix_id: int, ids: list[int]) -> None:
    if not ids:
        return

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM mix_tracks WHERE mix_id=?", (mix_id,))
        allowed = {row[0] for row in cur.fetchall()}

        filtered = [tid for tid in ids if tid in allowed]
        if not filtered:
            return

        for pos, tid in enumerate(filtered, start=1):
            cur.execute(
                "UPDATE mix_tracks SET pos=? WHERE id=? AND mix_id=?",
                (pos, tid, mix_id)
            )

        conn.commit()

ensure_spotify_column()