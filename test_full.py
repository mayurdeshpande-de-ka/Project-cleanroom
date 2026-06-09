import psycopg2, os, time
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()

start = time.time()
cur.execute("SET statement_timeout = 600000") # 10 mins
cur.execute("SELECT DISTINCT state_abb, el_type, el_year FROM public.form20_summary_view")
rows = cur.fetchall()
print("Took", time.time() - start, "seconds")
print("Total unique combos in form20_summary_view:", len(rows))
print(rows[:10])
