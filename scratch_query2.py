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
cur.execute("SELECT DISTINCT state, el_type, el_year FROM public.ac_election_mapping")
rows = cur.fetchall()
print(f"ac_election_mapping: {len(rows)} rows, Time: {time.time() - start:.2f}s")
