#!/usr/bin/env python3
"""
Assembles chunked browser data into final JSON and CSV files.
Run after all chunks are saved.
"""
import json, csv, os, glob

chunk_files = sorted(glob.glob('/tmp/hk_chunk_*.json'))
print(f"Found {len(chunk_files)} chunk files")

all_rows = []
headers = None

for f in chunk_files:
    with open(f, encoding='utf-8') as fp:
        chunk = json.load(fp)
    if headers is None:
        headers = chunk['headers']
    all_rows.extend(chunk['rows'])
    print(f"  {f}: {len(chunk['rows'])} rows")

print(f"Total rows: {len(all_rows)}")
print(f"Headers: {len(headers)}")

# Save JSON
out = {'headers': headers, 'rows': all_rows, 'total': len(all_rows)}
with open('/Users/flakeliu/claude/hk_stocks_data.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("Saved hk_stocks_data.json")

# Save CSV
with open('/Users/flakeliu/claude/hk_stocks_data.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(all_rows)
print("Saved hk_stocks_data.csv")
print("Done!")
