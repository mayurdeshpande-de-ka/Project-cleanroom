import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
print([r[0] for r in cur.fetchall()])
