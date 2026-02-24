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

        conn.commit()

#MIXES#
def add_mix(title, youtube, soundcloud, cover_path, tags):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mixes (title, youtube, soundcloud, cover, tags)
            VALUES (?, ?, ?, ?, ?)
        """, (title, youtube, soundcloud, cover_path, tags))
        conn.commit()

def get_all_mixes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, youtube, soundcloud, cover, tags FROM mixes ORDER BY id DESC")
        return cur.fetchall()

def get_mix_by_id(mix_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, youtube, soundcloud, cover, tags FROM mixes WHERE id=?", (mix_id,))
        return cur.fetchone()

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

def update_mix_links(mix_id: int, youtube: str, soundcloud: str) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mixes
            SET youtube = ?, soundcloud = ?
            WHERE id = ?
        """, (youtube.strip(), soundcloud.strip(), mix_id))
        conn.commit()

def update_mix_cover(mix_id, cover_path):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE mixes SET cover=? WHERE id=?", (cover_path, mix_id))
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

def delete_mix_tracks_bulk(mix_id: int, ids: list[int]) -> bool:
    if not ids:
        return False

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM mix_tracks WHERE mix_id=? AND id IN ({','.join(['?']*len(ids))})",
            [mix_id] + ids
        )
        conn.commit()
    return True

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

def set_mix_tags(mix_id: int, tags) -> None:
    """
    Перезаписує теги міксу.
    Приймає або list[str], або рядок "tag1, tag2, tag3".
    """
    # 1) нормалізуємо в list[str]
    if tags is None:
        tags_list = []
    elif isinstance(tags, str):
        tags_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    else:
        # очікуємо list/tuple/set
        tags_list = [str(t).strip().lower() for t in tags if str(t).strip()]

    with get_connection() as conn:
        cur = conn.cursor()

        # 2) чистимо зв’язки для цього міксу
        cur.execute("DELETE FROM mix_tags WHERE mix_id = ?", (mix_id,))

        # 3) додаємо теги і зв’язки
        for name in tags_list:
            cur.execute("SELECT id FROM tags WHERE name = ?", (name,))
            tag_id = cur.fetchone()[0]
            cur.execute(
                "INSERT OR IGNORE INTO mix_tags(mix_id, tag_id) VALUES(?, ?)",
                (mix_id, tag_id),
            )

        conn.commit()

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

def get_schema_version(conn):
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    cur.execute("SELECT version FROM schema_version LIMIT 1")
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO schema_version(version) VALUES (1)")
        conn.commit()
        return 1
    return row[0]

def set_schema_version(conn, v):
    cur = conn.cursor()
    cur.execute("UPDATE schema_version SET version = ?", (v,))
    conn.commit()

def normalize_tags(raw: str) -> list[str]:
    tags_list = [t.strip().lower() for t in raw.split(",") if t.strip()]
    # прибираємо дублікати, але зберігаємо порядок
    seen = set()
    result = []
    for t in tags_list:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result

def migrate_tags_from_column():
    """Одноразово переносить mixes.tags -> tags + mix_tags. Не шкодить, якщо запустити повторно."""
    with get_connection() as conn:
        cur = conn.cursor()

        # беремо всі мікси, де tags не порожній
        cur.execute("SELECT id, tags FROM mixes WHERE tags IS NOT NULL AND TRIM(tags) != ''")
        rows = cur.fetchall()

        for mix_id, raw in rows:
            set_mix_tags(mix_id, raw)

        conn.commit()

def get_all_tags_with_counts():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.name, COUNT(mt.mix_id) as cnt
            FROM tags t
            LEFT JOIN mix_tags mt ON mt.tag_id = t.id
            GROUP BY t.id, t.name
            ORDER BY t.name
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

def update_mix_tags(mix_id: int, tags: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE mixes SET tags = ? WHERE id = ?", (tags, mix_id))
        conn.commit()

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

def set_tracks_order(mix_id: int, ordered_ids: list[int]) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        for idx, track_id in enumerate(ordered_ids, start=1):
            cur.execute(
                "UPDATE mix_tracks SET pos=? WHERE id=? AND mix_id=?",
                (idx, track_id, mix_id)
            )
        conn.commit()