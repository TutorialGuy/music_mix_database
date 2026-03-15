from database import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT LOWER(TRIM(artist)), COUNT(*) as cnt
        FROM mix_tracks
        WHERE artist IS NOT NULL AND TRIM(artist) != ''
        GROUP BY LOWER(TRIM(artist))
        ORDER BY cnt DESC
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(row)