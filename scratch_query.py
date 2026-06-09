import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    dbname=os.environ.get('DB_NAME')
)

cur = conn.cursor()
cur.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema='public'")
for row in cur.fetchall():
    print(row)
