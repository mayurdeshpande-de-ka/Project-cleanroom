"""
update_turso_downloads.py
─────────────────────────
Reads 'Form 20 Download Report for Allotted States.csv' and updates
download_status (and conditionally overall_status / remark) in local data.db.

Rules
─────
• Present  → download_status = 'downloaded'
             If current overall_status == 'missing'  → upgrade overall_status to 'downloaded'
             Clear remark ONLY if the existing remark is null/empty (don't overwrite real notes)
• Missing  → download_status = 'missing'
             overall_status  unchanged
             Write Jira Note into remark ONLY if existing remark is null/empty

Run from the project root:
    python update_turso_downloads.py
"""

import csv
import os
import sqlite3
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'Form 20 Download Report for Allotted States.csv')
DB_PATH  = os.path.join(BASE_DIR, 'data.db')

# ── Sanity checks ─────────────────────────────────────────────────────────────

if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
if not os.path.exists(DB_PATH):
    raise FileNotFoundError(f"DB not found: {DB_PATH}")

# ── Load CSV ──────────────────────────────────────────────────────────────────

csv_rows = []
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        state    = str(row.get('State Code', '')).strip()
        election = str(row.get('Election',   '')).strip()
        year     = str(row.get('Year',       '')).strip()
        status   = str(row.get('Drive Status', '')).strip()
        note     = str(row.get('Jira Note',  '')).strip()
        if not (state and election and year):
            continue
        key = f'{state}-{election}-{year}'
        csv_rows.append({
            'key':    key,
            'status': status,   # 'Present' or 'Missing'
            'note':   note,
        })

print(f"CSV rows loaded : {len(csv_rows)}")
print(f"  Present : {sum(1 for r in csv_rows if r['status'] == 'Present')}")
print(f"  Missing : {sum(1 for r in csv_rows if r['status'] == 'Missing')}")
print()

# ── Connect to SQLite ─────────────────────────────────────────────────────────

# isolation_level=None = autocommit: each UPDATE commits immediately,
# avoiding the implicit BEGIN that competes with Flask's open WAL reader.
conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
conn.row_factory = sqlite3.Row
c = conn.cursor()
# WAL mode already set by Flask; this is a no-op but harmless
c.execute('PRAGMA journal_mode=WAL')

# ── Process each CSV row ──────────────────────────────────────────────────────

today = datetime.now().strftime('%Y-%m-%d')

updated_downloaded = 0   # rows where download_status set to 'downloaded'
updated_missing    = 0   # rows where download_status set to 'missing'
skipped_no_match   = 0   # CSV key not found in DB
status_upgraded    = 0   # overall_status promoted from 'missing' → 'downloaded'
remark_set         = 0   # remark written for missing records

for row in csv_rows:
    key         = row['key']
    drive_status = row['status']
    jira_note   = row['note']

    # ── Fetch existing DB record ──────────────────────────────────────────
    existing = c.execute(
        'SELECT id, overall_status, download_status, remark FROM records WHERE key = ?',
        (key,)
    ).fetchone()

    if existing is None:
        print(f"  [SKIP] No DB record for key: {key}")
        skipped_no_match += 1
        continue

    rec_id          = existing['id']
    cur_overall     = existing['overall_status']
    cur_dl          = existing['download_status']
    cur_remark      = existing['remark']      # may be None or empty string

    remark_is_empty = (cur_remark is None or str(cur_remark).strip() == '')

    # ── Build UPDATE fields ───────────────────────────────────────────────
    fields = {}
    fields['last_updated'] = today

    if drive_status == 'Present':
        # Always set download_status → 'downloaded'
        fields['download_status'] = 'downloaded'

        # Upgrade overall_status only if currently 'missing'
        if cur_overall == 'missing':
            fields['overall_status'] = 'downloaded'
            status_upgraded += 1

        # Clear remark only if it was null/empty (don't overwrite real notes)
        # (nothing to do — we leave the existing remark as-is)

        updated_downloaded += 1

    elif drive_status == 'Missing':
        # Set download_status → 'missing'
        fields['download_status'] = 'missing'

        # Store Jira Note in remark ONLY if existing remark is null/empty
        if remark_is_empty and jira_note:
            fields['remark'] = jira_note
            remark_set += 1

        # overall_status stays unchanged
        updated_missing += 1

    else:
        print(f"  [WARN] Unknown Drive Status '{drive_status}' for key {key} — skipped")
        continue

    # ── Execute UPDATE ────────────────────────────────────────────────────
    set_clause = ', '.join(f'{col} = ?' for col in fields)
    values     = list(fields.values()) + [rec_id]
    c.execute(f'UPDATE records SET {set_clause} WHERE id = ?', values)


conn.close()  # autocommit mode: each UPDATE already committed individually

# ── Summary ───────────────────────────────────────────────────────────────────

print("=" * 50)
print("UPDATE COMPLETE")
print("=" * 50)
print(f"  CSV rows processed  : {len(csv_rows)}")
print(f"  Skipped (no DB match): {skipped_no_match}")
print(f"  Set -> downloaded    : {updated_downloaded}")
print(f"  Set -> missing       : {updated_missing}")
print(f"  overall_status ^    : {status_upgraded}  (missing -> downloaded)")
print(f"  Remarks written     : {remark_set}")
print()
print(f"  DB: {DB_PATH}")
print("Done.")
