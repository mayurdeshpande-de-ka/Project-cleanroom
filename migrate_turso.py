import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()
turso_url = os.environ.get('TURSO_DATABASE_URL').replace('libsql://', 'https://')
turso_token = os.environ.get('TURSO_AUTH_TOKEN')
print("Connecting to Turso:", turso_url)
client = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)
try:
    client.execute('ALTER TABLE records ADD COLUMN manual_override INTEGER DEFAULT 0')
    print("Altered Turso!")
except Exception as e:
    print("Error:", e)

try:
    rs = client.execute("PRAGMA table_info(records)")
    print([r[1] for r in rs.rows])
except Exception as e:
    print("Error getting schema:", e)
