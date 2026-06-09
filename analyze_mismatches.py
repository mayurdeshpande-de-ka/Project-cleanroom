import json
import sqlite3
import os

def check_mismatches():
    db_path = 'data.db'
    json_path = 'live_extracted.json'

    # Load JSON
    with open(json_path, 'r') as f:
        live_data = json.load(f)

    # Load DB keys
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT state, el_type, el_year, key FROM records")
    db_records = c.fetchall()
    
    db_keys = {row[3]: row for row in db_records}
    
    # Match logic
    matched = 0
    mismatched = []

    for item in live_data:
        state = str(item.get('state', '')).strip()
        el_type = str(item.get('el_type', '')).strip()
        el_year = str(item.get('el_year', '')).strip()
        
        expected_key = f"{state}-{el_type}-{el_year}"
        if expected_key in db_keys:
            matched += 1
        else:
            mismatched.append(item)
    
    print(f"Total in JSON: {len(live_data)}")
    print(f"Matched: {matched}")
    print(f"Mismatched: {len(mismatched)}")
    
    # Let's find out why they mismatched. We can search for the state and year in db_records
    for item in mismatched:
        state = str(item.get('state', '')).strip()
        el_year = str(item.get('el_year', '')).strip()
        el_type = str(item.get('el_type', '')).strip()
        
        # Try finding state + year in DB
        possible_matches = []
        for db_state, db_el_type, db_el_year, db_key in db_records:
            if str(db_state).strip() == state and str(db_el_year).strip() == el_year:
                possible_matches.append(db_key)
        
        print(f"Missing in DB: {state}-{el_type}-{el_year} -> Possible DB matches: {possible_matches}")

if __name__ == "__main__":
    check_mismatches()
