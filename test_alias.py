from database import get_connection
from datetime import datetime

today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("UPDATE mixes SET added_at=? WHERE added_at IS NULL", (today,))
    updated = cur.rowcount
    conn.commit()

print(f"Оновлено міксів: {updated}")