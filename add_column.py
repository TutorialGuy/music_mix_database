import sqlite3

conn = sqlite3.connect('music.db')
try:
    conn.execute("ALTER TABLE mixes ADD COLUMN added_at TEXT")
    conn.commit()
    print("OK — колонка added_at додана")
except sqlite3.OperationalError as e:
    print(f"Помилка: {e}")
finally:
    conn.close()
