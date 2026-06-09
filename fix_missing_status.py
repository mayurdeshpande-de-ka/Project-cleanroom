import sqlite3, os

conn = sqlite3.connect('data.db', isolation_level=None)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Fix: records with download_status=missing should have overall_status=missing
# Only if not already at a higher stage (extracted, db_pushed, completed)
c.execute("""
    UPDATE records 
    SET overall_status = 'missing'
    WHERE download_status = 'missing' 
    AND overall_status NOT IN ('extracted', 'db_pushed', 'completed')
""")
print(f'Fixed {c.rowcount} records: overall_status set to missing')

print("\n=== Updated overall_status breakdown ===")
for r in c.execute("SELECT overall_status, COUNT(*) as cnt FROM records GROUP BY overall_status ORDER BY cnt DESC").fetchall():
    print(dict(r))

conn.close()
print("Done.")
