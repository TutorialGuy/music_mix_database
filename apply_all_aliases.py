from database import get_connection, get_mix_tags, set_mix_tags

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM mixes")
    mixes = cur.fetchall()

updated = 0
for mix_id, title in mixes:
    tags = get_mix_tags(mix_id)
    if tags:
        set_mix_tags(mix_id, tags)
        updated += 1

print(f"Готово! Оновлено міксів: {updated} з {len(mixes)}")