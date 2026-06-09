import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', '5432'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'form20_summary_view';")
print('form20_summary_view columns:', cur.fetchall())
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'ac_election_mapping';")
print('ac_election_mapping columns:', cur.fetchall())
conn.close()
