import psycopg2
import os
import time
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    dbname=os.environ.get('DB_NAME')
)
cur = conn.cursor()
start = time.time()
cur.execute("SELECT * FROM public.form20_summary_view WHERE state_abb = 'TN' and el_id = 53 LIMIT 1")
row = cur.fetchone()
print(f"Time for 1 query: {time.time()-start:.3f}s. Row: {row}")
