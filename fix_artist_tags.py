import sqlite3

conn = sqlite3.connect('music.db')
cur = conn.cursor()

cur.execute("SELECT id, name FROM tags WHERE name LIKE 'artist:%'")
rows = cur.fetchall()

fixed = 0
for tag_id, name in rows:
    if name.startswith('artist:') and not name.startswith('artist: '):
        new_name = 'artist: ' + name[7:]
        cur.execute("UPDATE tags SET name=? WHERE id=?", (new_name, tag_id))
        print(f"  '{name}' -> '{new_name}'")
        fixed += 1

conn.commit()
conn.close()
print(f"\nГотово! Виправлено: {fixed}")