import sqlite3
import os
import libsql_client

URL = "https://form-20-backlogdb-mayur-va-de.aws-ap-south-1.turso.io"
TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3Nzk4Njg3NDQsImlkIjoiMDE5ZTY4NzAtMmIwMS03YjgyLTgzNDEtM2EyZTA1Y2U3MjYzIiwicmlkIjoiNDQ2NTJjNmUtODQ1Yy00YWM4LWEzMjYtYzNlNTc1NWNkZTUxIn0.01xMd0Sj53-PCJyVxd8welYEQrgLS37k4kMrVwddE7OThTBTMDw8clJJqSybL5qg7pugrPsZicee050ZTf1PCw"

def main():
    print("Connecting to local SQLite...")
    local_conn = sqlite3.connect('data.db')
    local_conn.row_factory = sqlite3.Row

    print("Connecting to Turso...")
    client = libsql_client.create_client_sync(url=URL, auth_token=TOKEN)

    print("Creating tables on Turso...")
    client.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            state               TEXT NOT NULL,
            state_name          TEXT,
            el_type             TEXT NOT NULL,
            el_year             INTEGER NOT NULL,
            key                 TEXT UNIQUE NOT NULL,
            is_sir_state        INTEGER DEFAULT 0,
            download_status     TEXT DEFAULT 'missing',
            extraction_status   TEXT DEFAULT 'pending',
            db_status           TEXT DEFAULT 'not_in_db',
            overall_status      TEXT DEFAULT 'missing',
            wip                 INTEGER DEFAULT 0,
            assigned_to         TEXT,
            remark              TEXT,
            last_updated        TEXT,
            retro_ready         INTEGER DEFAULT 0,
            created_at          TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    client.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            record_key  TEXT,
            action      TEXT,
            old_value   TEXT,
            new_value   TEXT,
            changed_by  TEXT,
            timestamp   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    print("Fetching local records...")
    records = local_conn.execute("SELECT * FROM records").fetchall()
    print(f"Found {len(records)} records. Uploading to Turso...")

    if records:
        cols = records[0].keys()
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(cols))
        query = f"INSERT OR REPLACE INTO records ({cols_str}) VALUES ({placeholders})"
        
        stmts = []
        for idx, r in enumerate(records):
            args = list(r)
            stmts.append(libsql_client.Statement(query, args))
        
        batch_size = 100
        for i in range(0, len(stmts), batch_size):
            client.batch(stmts[i:i+batch_size])
            print(f"Uploaded {min(i+batch_size, len(stmts))}/{len(stmts)}...")

    print("Fetching local activity_log...")
    logs = local_conn.execute("SELECT * FROM activity_log").fetchall()
    if logs:
        cols = logs[0].keys()
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(cols))
        query = f"INSERT OR REPLACE INTO activity_log ({cols_str}) VALUES ({placeholders})"
        
        stmts = []
        for r in logs:
            stmts.append(libsql_client.Statement(query, list(r)))
            
        if stmts:
            batch_size = 100
            for i in range(0, len(stmts), batch_size):
                client.batch(stmts[i:i+batch_size])

    print("Migration complete!")
    local_conn.close()
    client.close()

if __name__ == "__main__":
    main()
