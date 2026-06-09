import json

with open('completion_history.json', 'r') as f:
    data = json.load(f)

true_tracked = {
  "AP-GE-2009": "2026-06-02",
  "AP-GE-2014": "2026-06-02",
  "AP-GE-2019": "2026-06-03",
  "AP-AE-2019": "2026-06-04",
  "GJ-GE-2019": "2026-06-04",
  "GJ-GE-2024": "2026-06-05",
  "MP-AE-2023": "2026-06-06",
  "TS-GE-2009": "2026-06-07"
}

count_fixed = 0
for k in data.keys():
    if k == "_updated": continue
    if k in true_tracked:
        data[k] = true_tracked[k]
    else:
        # Extract year from key (e.g. AP-GE-2014 -> 2014, AP-AE-BP-2019 -> 2019)
        parts = k.split('-')
        year = parts[-1]
        if year.isdigit() and len(year) == 4:
            # Set it to end of that year so it's historical
            data[k] = f"{year}-12-31"
            count_fixed += 1

with open('completion_history.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Fixed {count_fixed} records to their historical years. Kept {len(true_tracked)} manual tracking entries.")
