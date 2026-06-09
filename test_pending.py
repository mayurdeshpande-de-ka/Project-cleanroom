import sqlite3, json

conn = sqlite3.connect('data.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM records").fetchall()

with open('download_report.json') as f:
    download_report = json.load(f)

with open('live_extracted.json') as f:
    live_extracted_raw = json.load(f)
    live_extracted = set((str(item['state']).strip(), str(item['el_type']).strip(), str(item['el_year']).strip()) for item in live_extracted_raw)

pending_count = 0
downloaded_count = 0
for r in rows:
    r_dict = dict(r)
    key = f"{str(r_dict['state']).strip()}-{str(r_dict['el_type']).strip()}-{str(r_dict['el_year']).strip()}"
    current_status = r_dict.get('overall_status')
    
    if key in download_report:
        csv_status = download_report[key]
        if current_status not in ('db_pushed', 'completed', 'extracted'):
            r_dict['overall_status'] = csv_status
    else:
        if current_status not in ('db_pushed', 'completed', 'extracted'):
            r_dict['overall_status'] = 'pending'
            
    aws_el_type = str(r_dict['el_type']).strip().replace('-BP', '')
    is_live_completed = (str(r_dict['state']).strip(), aws_el_type, str(r_dict['el_year']).strip()) in live_extracted
    if is_live_completed:
        r_dict['overall_status'] = 'completed'
        
    if r_dict['overall_status'] == 'pending': pending_count += 1
    if r_dict['overall_status'] == 'downloaded': downloaded_count += 1

print(f"Pending count would be: {pending_count}")
print(f"Downloaded count would be: {downloaded_count}")
