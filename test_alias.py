from database import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM tags WHERE name LIKE 'artist:  %'")
    rows = cur.fetchall()
    for tag_id, name in rows:
        fixed = 'artist: ' + name[8:].strip()
        print(f"  '{name}' -> '{fixed}'")
        cur.execute("UPDATE tags SET name=? WHERE id=?", (fixed, tag_id))
    conn.commit()
    print(f"Виправлено: {len(rows)}")