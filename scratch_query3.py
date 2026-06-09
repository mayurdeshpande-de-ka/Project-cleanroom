import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import DictCursor

load_dotenv()

def get_rds_db():
    db_host = os.environ.get('DB_HOST')
    db_port = os.environ.get('DB_PORT', '5432')
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASSWORD')
    db_name = os.environ.get('DB_NAME')
    
    if not all([db_host, db_user, db_pass, db_name]):
        return None
        
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_pass,
        dbname=db_name
    )
    return conn

conn = get_rds_db()
if conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT (state_abb, el_type, el_year)) FROM public.form20_summary_view")
        print("Form20:", cur.fetchone())
        
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT (state_abb, el_type, el_year)) FROM public.ac_election_mapping")
        print("AC-PC mapping:", cur.fetchone())
else:
    print("No DB conn")
