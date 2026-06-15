import app
import json

def check_cache():
    live_data_str = app.cache_get('live')
    if not live_data_str:
        print("No live data found in cache.")
        return
        
    live_data = json.loads(live_data_str)
    
    records_to_check = [
        ("TS", "GE", "2009"),
        ("TS", "AE", "2023"),
        ("AP", "AE", "2009"),
        ("MP", "GE", "2019"),
        ("TS", "AE", "2009"),
        ("AP", "AE", "2014")
    ]
    
    # live_data is a list of dicts: {"state": "TS", "el_type": "GE", "el_year": "2009"}
    found_records = set()
    for row in live_data:
        state = row.get("state")
        etype = row.get("el_type")
        eyear = str(row.get("el_year"))
        
        for r in records_to_check:
            if state == r[0] and etype == r[1] and eyear == r[2]:
                found_records.add(f"{state}-{etype}-{eyear}")
                
    print("Verification Results in Application Cache:")
    print("-" * 50)
    for state, etype, eyear in records_to_check:
        rec_id = f"{state}-{etype}-{eyear}"
        if rec_id in found_records:
            print(f"✅ {rec_id}: Present in Cache (which mirrors RDS)")
        else:
            print(f"❌ {rec_id}: NOT PRESENT in Cache")

if __name__ == '__main__':
    check_cache()
