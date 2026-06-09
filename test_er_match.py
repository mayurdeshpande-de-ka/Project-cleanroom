import json, sqlite3, psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = sqlite3.connect('data.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT state, el_type, el_year FROM records").fetchall()

pg_conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = pg_conn.cursor()
cur.execute("SELECT DISTINCT r.state_abb, e.el_type, e.el_year FROM election_result r JOIN election e ON r.el_id = e.el_id")
er_list = set((r[0], r[1], str(r[2])) for r in cur.fetchall())

matches1 = 0
matches2 = 0
for r in rows:
    tup = (str(r['state']).strip(), str(r['el_type']).strip(), str(r['el_year']).strip())
    aws_tup = (str(r['state']).strip(), str(r['el_type']).strip().replace('-BP',''), str(r['el_year']).strip())
    if tup in er_list: matches1 += 1
    if aws_tup in er_list: matches2 += 1

print(f"Direct ER matches: {matches1}")
print(f"Stripped ER matches: {matches2}")
