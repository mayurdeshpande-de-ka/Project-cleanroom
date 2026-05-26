import csv
import time
import os

retro_path = 'd:\\Others\\Varahe Work\\Tasks\\Form 20 Backlog Dashboard\\RETRO.csv'
metadata = {}

start = time.time()
with open(retro_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)
    state_idx = headers.index('state_abb')
    type_idx = headers.index('el_type')
    year_idx = headers.index('el_year')

    for row in reader:
        if len(row) > max(state_idx, type_idx, year_idx):
            s = row[state_idx].strip()
            t = row[type_idx].strip()
            y = row[year_idx].strip()
            if not s or not t or not y:
                continue
            
            if s not in metadata:
                metadata[s] = {}
            if t not in metadata[s]:
                metadata[s][t] = {}
            if y not in metadata[s][t]:
                metadata[s][t][y] = 0
            metadata[s][t][y] += 1

print(f"Parsed in {time.time() - start:.2f} seconds")
print(f"Total states: {len(metadata)}")
