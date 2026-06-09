import json
import os

live_json_path = 'live_extracted.json'

if os.path.exists(live_json_path):
    with open(live_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    years = set()
    for item in data:
        if '-BP' not in item.get('el_type', ''):
            years.add(int(item.get('el_year')))
            
    print("Non-BP Years present in Form 20:")
    print(sorted(list(years)))
else:
    print("live_extracted.json not found. The background task may not have completed its sync yet.")
