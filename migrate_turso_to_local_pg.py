import os, psycopg2, libsql_client
from dotenv import load_dotenv

def main():
    load_dotenv('.env')
    print('Connecting to Turso...')
    turso_url = os.environ.get('TURSO_DATABASE_URL').replace('libsql://', 'https://')
    turso_token = os.environ.get('TURSO_AUTH_TOKEN')
    t_client = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)
    
    print('Connecting to Local Postgres...')
    pg_conn = psycopg2.connect(
        host='localhost',
        user='backlog_user',
        password='backlog_local_pass',
        database='local_backlog_db'
    )
    pg_cur = pg_conn.cursor()
    
    print('Creating tables in Local Postgres...')
    pg_cur.execute('''
        CREATE TABLE IF NOT EXISTS download_tracking (
            id SERIAL PRIMARY KEY,
            assembly_constituency TEXT NOT NULL,
            state TEXT NOT NULL,
            type TEXT NOT NULL,
            record_key TEXT UNIQUE NOT NULL,
            is_sir_state INTEGER DEFAULT 0,
            download_status TEXT DEFAULT 'missing',
            extraction_status TEXT DEFAULT 'pending',
            db_status TEXT DEFAULT 'not_in_db',
            overall_status TEXT DEFAULT 'missing',
            wip INTEGER DEFAULT 0,
            assigned_to TEXT,
            remark TEXT,
            last_updated TEXT,
            retro_ready INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            manual_override INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            record_key TEXT,
            action TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    print('Migrating download_tracking...')
    res = t_client.execute('SELECT * FROM download_tracking')
    if res.rows:
        cols = ', '.join(res.columns)
        placeholders = ', '.join(['%s'] * len(res.columns))
        # Insert avoiding duplicate ID conflicts
        insert_query = f'INSERT INTO download_tracking ({cols}) VALUES ({placeholders}) ON CONFLICT (record_key) DO NOTHING'
        pg_cur.executemany(insert_query, [list(r) for r in res.rows])
        # Update sequence
        pg_cur.execute("SELECT setval('download_tracking_id_seq', COALESCE((SELECT MAX(id) FROM download_tracking), 1));")
    
    print('Migrating activity_log...')
    res2 = t_client.execute('SELECT * FROM activity_log')
    if res2.rows:
        cols2 = ', '.join(res2.columns)
        placeholders2 = ', '.join(['%s'] * len(res2.columns))
        # activity_log doesn't have a unique constraint besides ID, so we avoid conflict on ID if migrating multiple times
        insert_query2 = f'INSERT INTO activity_log ({cols2}) VALUES ({placeholders2}) ON CONFLICT (id) DO NOTHING'
        pg_cur.executemany(insert_query2, [list(r) for r in res2.rows])
        pg_cur.execute("SELECT setval('activity_log_id_seq', COALESCE((SELECT MAX(id) FROM activity_log), 1));")
        
    pg_conn.commit()
    print('Migration complete!')

if __name__ == '__main__':
    main()
