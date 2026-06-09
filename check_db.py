import sqlite3, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
conn = sqlite3.connect(os.path.join(BASE_DIR, 'data.db'))
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== download_status breakdown ===")
for r in c.execute("SELECT download_status, COUNT(*) as cnt FROM records GROUP BY download_status").fetchall():
    print(dict(r))

print("\n=== overall_status breakdown ===")
for r in c.execute("SELECT overall_status, COUNT(*) as cnt FROM records GROUP BY overall_status").fetchall():
    print(dict(r))

print("\n=== Sample MISSING records ===")
for r in c.execute("SELECT key, download_status, overall_status, remark FROM records WHERE download_status='missing' LIMIT 10").fetchall():
    print(dict(r))

conn.close()
