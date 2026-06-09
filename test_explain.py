import psycopg2, os, time
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()

start = time.time()
cur.execute("""
    EXPLAIN SELECT DISTINCT el_id, state_abb FROM public.form20_summary_view
""")
rows = cur.fetchall()
for r in rows:
    print(r[0])
