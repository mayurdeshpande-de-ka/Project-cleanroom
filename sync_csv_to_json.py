import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'Form 20 Download Report for Allotted States.csv')
JSON_PATH = os.path.join(BASE_DIR, 'download_report.json')

def update_download_json():
    if not os.path.exists(CSV_PATH):
        return
        
    download_data = {}
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = str(row.get('State Code', '')).strip()
            election = str(row.get('Election', '')).strip()
            year = str(row.get('Year', '')).strip()
            status = str(row.get('Drive Status', '')).strip()
            
            if not (state and election and year):
                continue
                
            key = f"{state}-{election}-{year}"
            
            if status == 'Present':
                download_data[key] = 'downloaded'
            elif status == 'Missing':
                download_data[key] = 'missing'
                
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(download_data, f, indent=2)
    print(f"Updated {JSON_PATH} with {len(download_data)} records.")

if __name__ == '__main__':
    update_download_json()
