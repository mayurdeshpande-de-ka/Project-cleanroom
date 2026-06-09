import json, sqlite3, os
DB_PATH = 'data.db'
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM records WHERE state='TN' AND el_year=2014 AND el_type='GE'").fetchall()
r_dict = dict(rows[0])
print("DB r_dict:", r_dict)

with open('live_extracted.json') as f:
    extracted = json.load(f)
live_set = set((item['state'], item['el_type'], item['el_year']) for item in extracted)

print("live_set contains TN GE 2014 as string?", ('TN', 'GE', '2014') in live_set)
print("live_set contains TN GE 2014 as int?", ('TN', 'GE', 2014) in live_set)

test_tuple = (str(r_dict['state']).strip(), str(r_dict['el_type']).strip(), str(r_dict['el_year']).strip())
print("test_tuple:", test_tuple)
print("Match?", test_tuple in live_set)

print("Why only 6 completed?")
for r in conn.execute("SELECT state, el_type, el_year, overall_status FROM records WHERE overall_status='completed'").fetchall():
    print(dict(r))
