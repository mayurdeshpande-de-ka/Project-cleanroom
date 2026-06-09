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
cur.execute("SELECT DISTINCT state_abb, el_id FROM form_20")
rows = cur.fetchall()
print(f"Time: {time.time()-start:.2f}s, Rows: {len(rows)}")
