"""
sync_downloads_to_turso.py
──────────────────────────
1. Reads the CSV report for downloaded/missing status
2. Fixes local data.db
3. Pushes the exact same changes to Turso

Safe rules:
- Present  → download_status='downloaded', overall_status upgraded ONLY if currently 'missing'
- Missing  → download_status='missing', overall_status set to 'missing' if NOT extracted/db_pushed/completed
             Jira Note written to remark ONLY if existing remark is null/empty
"""

import csv
import os
import sqlite3
from datetime import datetime
import libsql_client

# ── Credentials ───────────────────────────────────────────────────────────────
TURSO_URL   = "https://form-20-backlogdb-mayur-va-de.aws-ap-south-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3Nzk4Njg3NDQsImlkIjoiMDE5ZTY4NzAtMmIwMS03YjgyLTgzNDEtM2EyZTA1Y2U3MjYzIiwicmlkIjoiNDQ2NTJjNmUtODQ1Yy00YWM4LWEzMjYtYzNlNTc1NWNkZTUxIn0.01xMd0Sj53-PCJyVxd8welYEQrgLS37k4kMrVwddE7OThTBTMDw8clJJqSybL5qg7pugrPsZicee050ZTf1PCw"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'Form 20 Download Report for Allotted States.csv')
DB_PATH  = os.path.join(BASE_DIR, 'data.db')
TODAY    = datetime.now().strftime('%Y-%m-%d')

SAFE_STATUSES = ('extracted', 'db_pushed', 'completed')

# ── Load CSV ──────────────────────────────────────────────────────────────────
print("Reading CSV...")
csv_rows = []
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        state    = str(row.get('State Code', '')).strip()
        election = str(row.get('Election',   '')).strip()
        year     = str(row.get('Year',       '')).strip()
        status   = str(row.get('Drive Status', '')).strip()
        note     = str(row.get('Jira Note',  '')).strip()
        if not (state and election and year):
            continue
        csv_rows.append({
            'key':    f'{state}-{election}-{year}',
            'status': status,
            'note':   note,
        })

present_keys = {r['key'] for r in csv_rows if r['status'] == 'Present'}
missing_map  = {r['key']: r['note'] for r in csv_rows if r['status'] == 'Missing'}

print(f"  Present : {len(present_keys)}")
print(f"  Missing : {len(missing_map)}")

# ── Fix local data.db ─────────────────────────────────────────────────────────
print("\nFixing local data.db...")
lconn = sqlite3.connect(DB_PATH, isolation_level=None)
lconn.row_factory = sqlite3.Row
lc = lconn.cursor()

local_dl_fixed  = 0
local_mi_fixed  = 0

for key in present_keys:
    row = lc.execute("SELECT id, overall_status FROM records WHERE key=?", (key,)).fetchone()
    if not row: continue
    fields = {'download_status': 'downloaded', 'last_updated': TODAY}
    if row['overall_status'] == 'missing':
        fields['overall_status'] = 'downloaded'
    set_c = ', '.join(f'{k}=?' for k in fields)
    lc.execute(f"UPDATE records SET {set_c} WHERE id=?", list(fields.values()) + [row['id']])
    local_dl_fixed += 1

for key, note in missing_map.items():
    row = lc.execute("SELECT id, overall_status, remark FROM records WHERE key=?", (key,)).fetchone()
    if not row: continue
    fields = {'download_status': 'missing', 'last_updated': TODAY}
    if row['overall_status'] not in SAFE_STATUSES:
        fields['overall_status'] = 'missing'
    if note and not (row['remark'] and str(row['remark']).strip()):
        fields['remark'] = note
    set_c = ', '.join(f'{k}=?' for k in fields)
    lc.execute(f"UPDATE records SET {set_c} WHERE id=?", list(fields.values()) + [row['id']])
    local_mi_fixed += 1

lconn.close()
print(f"  Local -> downloaded fixed : {local_dl_fixed}")
print(f"  Local -> missing fixed    : {local_mi_fixed}")

# ── Fix Turso ─────────────────────────────────────────────────────────────────
print("\nConnecting to Turso...")
client = libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

# Fetch all current Turso records once
print("Fetching Turso records...")
result = client.execute("SELECT id, key, overall_status, download_status, remark FROM records")
cols   = result.columns
turso_records = {row[cols.index('key')]: dict(zip(cols, row)) for row in result.rows}
print(f"  Loaded {len(turso_records)} Turso records")

stmts = []

for key in present_keys:
    rec = turso_records.get(key)
    if not rec: continue
    new_overall = 'downloaded' if rec['overall_status'] == 'missing' else rec['overall_status']
    stmts.append(libsql_client.Statement(
        "UPDATE records SET download_status=?, overall_status=?, last_updated=? WHERE id=?",
        ['downloaded', new_overall, TODAY, rec['id']]
    ))

for key, note in missing_map.items():
    rec = turso_records.get(key)
    if not rec: continue
    new_overall = rec['overall_status'] if rec['overall_status'] in SAFE_STATUSES else 'missing'
    cur_remark  = rec.get('remark') or ''
    new_remark  = note if (note and not cur_remark.strip()) else cur_remark
    stmts.append(libsql_client.Statement(
        "UPDATE records SET download_status=?, overall_status=?, remark=?, last_updated=? WHERE id=?",
        ['missing', new_overall, new_remark, TODAY, rec['id']]
    ))

print(f"\nPushing {len(stmts)} updates to Turso in batches...")
BATCH = 80
for i in range(0, len(stmts), BATCH):
    client.batch(stmts[i:i+BATCH])
    done = min(i+BATCH, len(stmts))
    print(f"  {done}/{len(stmts)} done...")

client.close()

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("SYNC COMPLETE")
print("="*50)
print(f"  CSV rows processed  : {len(csv_rows)}")
print(f"  Turso updates sent  : {len(stmts)}")
print(f"    -> downloaded      : {len(present_keys)}")
print(f"    -> missing         : {len(missing_map)}")
print("\nDone. Refresh your dashboard!")
