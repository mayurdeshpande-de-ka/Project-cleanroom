import psycopg2, os, time
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()

start = time.time()
cur.execute("SELECT 1 FROM form_20 f JOIN election e ON f.el_id = e.el_id WHERE e.el_type = 'GE' AND e.el_year = 2024 AND f.state_abb = 'AP' LIMIT 1")
print(cur.fetchone())
print("Took", time.time() - start, "seconds")
