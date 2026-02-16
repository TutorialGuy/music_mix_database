import sqlite3

DB_NAME = "music.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            youtube TEXT,
            soundcloud TEXT,
            cover TEXT
        )
        """)

        try:
            cursor.execute("ALTER TABLE mixes ADD COLUMN cover TEXT")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT,
            title TEXT NOT NULL,
            soundcloud TEXT,
            UNIQUE(artist, title)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mix_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mix_id INTEGER NOT NULL,
            track_id INTEGER,
            artist TEXT,
            title TEXT NOT NULL,
            soundcloud TEXT,
            time TEXT,
            pos INTEGER NOT NULL,
            FOREIGN KEY (mix_id) REFERENCES mixes(id)
        )
        """)

        try:
            cursor.execute("ALTER TABLE mix_tracks ADD COLUMN pos INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def add_mix(title, youtube, soundcloud, cover):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO mixes (title, youtube, soundcloud, cover) VALUES (?, ?, ?, ?)",
            (title, youtube, soundcloud, cover)
        )
        conn.commit()



def get_all_mixes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, youtube, soundcloud FROM mixes ORDER BY id DESC")
        return cursor.fetchall()

def get_mix_by_id(mix_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, youtube, soundcloud FROM mixes WHERE id=?", (mix_id,))
        return cur.fetchone()


def add_track_to_mix(mix_id, artist, title, soundcloud, time_value):
    artist = (artist or "").strip()
    title = (title or "").strip()
    soundcloud = (soundcloud or "").strip()
    time_value = (time_value or "").strip()

    # Назва треку обов'язкова
    if not title:
        return False

    artist_db = artist if artist else None
    soundcloud_db = soundcloud if soundcloud else None
    time_db = time_value if time_value else None

    with get_connection() as conn:
        cur = conn.cursor()

        # позиція = остання + 1
        cur.execute(
            "SELECT COALESCE(MAX(pos), 0) + 1 FROM mix_tracks WHERE mix_id=?",
            (mix_id,)
        )
        next_pos = cur.fetchone()[0]

        # додаємо рядок у mix_tracks (УСІ ДАНІ ТУТ)
        cur.execute(
            """
            INSERT INTO mix_tracks (mix_id, artist, title, soundcloud, time, pos)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (mix_id, artist_db, title, soundcloud_db, time_db, next_pos)
        )

        conn.commit()

    return True


    with get_connection() as conn:
        cur = conn.cursor()

        # 1) Вставляємо трек або отримуємо існуючий
        cur.execute(
            "INSERT OR IGNORE INTO tracks (artist, title) VALUES (?, ?)",
            (artist, title)
        )
        cur.execute(
            "SELECT id FROM tracks WHERE artist=? AND title=?",
            (artist, title)
        )
        track_id = cur.fetchone()[0]

        # 2) Прив'язуємо трек до міксу
        cur.execute(
            "INSERT OR IGNORE INTO mix_tracks (mix_id, track_id) VALUES (?, ?)",
            (mix_id, track_id)
        )
        conn.commit()


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

def get_mix_track_row(mix_track_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT id, mix_id, artist, title, soundcloud, time, pos
        FROM mix_tracks
        WHERE id = ?
        """, (mix_track_id,))
        return cur.fetchone()

def update_mix_track(mix_track_id, artist, title, soundcloud, time_value):
    artist = (artist or "").strip()
    title = (title or "").strip()
    soundcloud = (soundcloud or "").strip()
    time_value = (time_value or "").strip()

    if not title:
        return False

    artist_db = artist if artist else None
    soundcloud_db = soundcloud if soundcloud else None
    time_db = time_value if time_value else None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE mix_tracks
        SET artist=?, title=?, soundcloud=?, time=?
        WHERE id=?
        """, (artist_db, title, soundcloud_db, time_db, mix_track_id))
        conn.commit()

    return True

def delete_mix_track(mix_track_id):
    with get_connection() as conn:
        cur = conn.cursor()

        # дізнаємось mix_id та pos видаленого треку
        cur.execute("""
        SELECT mix_id, pos FROM mix_tracks WHERE id=?
        """, (mix_track_id,))
        row = cur.fetchone()

        if not row:
            return False

        mix_id, deleted_pos = row

        # видаляємо сам трек
        cur.execute("""
        DELETE FROM mix_tracks WHERE id=?
        """, (mix_track_id,))

        # зсуваємо всі треки нижче на -1
        cur.execute("""
        UPDATE mix_tracks
        SET pos = pos - 1
        WHERE mix_id=? AND pos > ?
        """, (mix_id, deleted_pos))

        conn.commit()

    return True



