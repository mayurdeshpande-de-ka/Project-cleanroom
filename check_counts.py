import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'), dbname=os.environ.get('DB_NAME'))
cur = conn.cursor()
tables = ['spatial_ref_sys', 'geography_columns', 'geometry_columns', 'ac_details', 'pg_stat_statements_info', 'pg_stat_statements', 'ac_election_mapping', 'alliance', 'alliance_parties', 'district', 'election', 'ac_mapping', 'election_result', 'party', 'pc_region', 'state', 'zone']
for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(t, cur.fetchone()[0])
    except Exception as e:
        conn.rollback()
        pass
