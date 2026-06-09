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
query = """
SELECT DISTINCT a.state_abb, e.el_type, e.el_year 
FROM election e 
JOIN ac_election_mapping a ON e.el_id = a.el_id 
WHERE EXISTS (
   SELECT 1 FROM form20_summary_view f 
   WHERE f.state_abb = a.state_abb AND f.el_id = a.el_id LIMIT 1
)
"""
cur.execute(query)
rows = cur.fetchall()
print(f"Rows: {len(rows)}, Time: {time.time()-start:.2f}s")
