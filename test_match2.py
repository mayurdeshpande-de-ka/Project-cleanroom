import json, sqlite3, os
DB_PATH = 'data.db'
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT state, el_type, el_year, overall_status FROM records WHERE state='TN'").fetchall()
for r in rows:
    print(dict(r))

with open('live_extracted.json') as f:
    extracted = json.load(f)
live_set = set((item['state'], item['el_type'], str(item['el_year'])) for item in extracted)

print("\nChecking matching...")
for r in rows:
    tup = (str(r['state']).strip(), str(r['el_type']).strip(), str(r['el_year']).strip())
    if tup in live_set:
        print("MATCHED:", tup)
