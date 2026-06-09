import json
import os

live_json_path = 'live_extracted.json'

if os.path.exists(live_json_path):
    with open(live_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Filter out BP if needed, but let's just show all and specify type
    # Sort by State, then Year, then Type
    filtered = [item for item in data if '-BP' not in item.get('el_type', '')]
    sorted_data = sorted(filtered, key=lambda x: (x.get('state', ''), int(x.get('el_year', 0)), x.get('el_type', '')))
    
    print("# Form 20 (DB Pushed) Elections\n")
    print("This table lists all unique `State`, `Year`, and `Election Type` combinations that are currently present in the Form 20 table. These are considered **DB Pushed**.\n")
    print("| State | Year | Election Type |")
    print("|-------|------|---------------|")
    for item in sorted_data:
        print(f"| {item.get('state')} | {item.get('el_year')} | {item.get('el_type')} |")
else:
    print("No data found.")
