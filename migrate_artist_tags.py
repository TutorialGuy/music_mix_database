from database import get_connection

def migrate():
    with get_connection() as conn:
        cur = conn.cursor()

        # отримуємо всі унікальні імена артистів з mix_tracks
        cur.execute("""
            SELECT DISTINCT LOWER(TRIM(artist))
            FROM mix_tracks
            WHERE artist IS NOT NULL AND TRIM(artist) != ''
        """)
        artist_names = {row[0] for row in cur.fetchall()}

        # отримуємо всі теги які збігаються з іменами артистів
        cur.execute("SELECT id, name FROM tags")
        all_tags = cur.fetchall()

        migrated = 0
        skipped = 0

        for tag_id, tag_name in all_tags:
            if tag_name.lower().strip() in artist_names:
                new_name = f"artist:{tag_name}"

                # перевіряємо чи тег з таким іменем вже існує
                cur.execute("SELECT id FROM tags WHERE name=?", (new_name,))
                existing = cur.fetchone()

                if existing:
                    # тег artist:xxx вже є — переносимо зв'язки на нього і видаляємо старий
                    cur.execute("""
                        UPDATE OR IGNORE mix_tags SET tag_id=?
                        WHERE tag_id=?
                    """, (existing[0], tag_id))
                    cur.execute("DELETE FROM mix_tags WHERE tag_id=?", (tag_id,))
                    cur.execute("DELETE FROM tags WHERE id=?", (tag_id,))
                    print(f"  злито: '{tag_name}' -> '{new_name}'")
                else:
                    # просто перейменовуємо
                    cur.execute("UPDATE tags SET name=? WHERE id=?", (new_name, tag_id))
                    print(f"  мігровано: '{tag_name}' -> '{new_name}'")

                migrated += 1
            else:
                skipped += 1

        conn.commit()
        print(f"\nГотово! Мігровано: {migrated}, пропущено: {skipped}")

if __name__ == "__main__":
    migrate()