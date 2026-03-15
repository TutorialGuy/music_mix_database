from database import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM tags WHERE name LIKE '%drum%n%bass%'")
    rows = cur.fetchall()
    for row in rows:
        print(repr(row))