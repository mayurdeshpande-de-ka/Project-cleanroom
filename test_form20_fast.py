import psycopg2, os, time
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()

start = time.time()
cur.execute("""
    SELECT DISTINCT f.state_abb, e.el_type, e.el_year 
    FROM form_20 f 
    JOIN election e ON f.el_id = e.el_id
""")
rows = cur.fetchall()
print("Took", time.time() - start, "seconds")
print("Total unique combos in form_20:", len(rows))
print(rows[:10])
