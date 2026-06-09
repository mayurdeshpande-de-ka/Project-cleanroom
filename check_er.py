import psycopg2, os, time
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='election_result'")
print([r[0] for r in cur.fetchall()])
