import psycopg2, os, json
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()
cur.execute("SELECT DISTINCT state_abb, el_type, el_year FROM public.form20_summary_view")
rows = cur.fetchall()
extracted_list = [{"state": str(r[0]).strip(), "el_type": str(r[1]).strip(), "el_year": str(r[2]).strip()} for r in rows if r[0] and r[1] and r[2]]
with open('live_extracted.json', 'w', encoding='utf-8') as f:
    json.dump(extracted_list, f)
print("Updated live_extracted.json with", len(extracted_list), "records.")
