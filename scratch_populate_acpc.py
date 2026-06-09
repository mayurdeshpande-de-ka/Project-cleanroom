import os, json
from dotenv import load_dotenv
load_dotenv()

import psycopg2

db_host = os.environ.get('DB_HOST')
db_port = os.environ.get('DB_PORT', '5432')
db_user = os.environ.get('DB_USER')
db_pass = os.environ.get('DB_PASSWORD')
db_name = os.environ.get('DB_NAME')

conn = psycopg2.connect(host=db_host, port=db_port, user=db_user, password=db_pass, dbname=db_name)
with conn.cursor() as cur:
    cur.execute("SELECT DISTINCT state_abb, el_type, el_year FROM public.ac_election_mapping")
    rds_acpc = cur.fetchall()
conn.close()

acpc_list = [{"state": str(r[0]).strip(), "el_type": str(r[1]).strip(), "el_year": str(r[2]).strip()} for r in rds_acpc if r[0] and r[1] and r[2]]
with open('ac_pc_extracted.json', 'w', encoding='utf-8') as f:
    json.dump(acpc_list, f)

print(f"Written {len(acpc_list)} AC-PC entries to ac_pc_extracted.json")

# Now test the stats
from collections import Counter

form20_set = set()
with open('live_extracted.json', encoding='utf-8') as f:
    for item in json.load(f):
        s, t, y = item.get('state','').strip(), item.get('el_type','').strip(), item.get('el_year','').strip()
        if s and t and y and '-BP' not in t:
            form20_set.add((s,t,y))

acpc_set = set()
for item in acpc_list:
    s, t, y = item.get('state','').strip(), item.get('el_type','').strip(), item.get('el_year','').strip()
    if s and t and y and '-BP' not in t:
        acpc_set.add((s,t,y))

type_f20   = Counter(t for _,t,_ in form20_set)
type_acpc  = Counter(t for _,t,_ in acpc_set)
all_types  = sorted(set(list(type_f20)+list(type_acpc)))

print(f"\nForm 20 entries (non-BP):       {len(form20_set)}")
print(f"AC-PC mapping entries (non-BP): {len(acpc_set)}")
pct = round(len(form20_set)/len(acpc_set)*100) if acpc_set else 0
print(f"Coverage: {pct}%")
print(f"Remaining: {len(acpc_set)-len(form20_set)}")
print(f"\nYears in Form 20 ({len(set(int(y) for _,_,y in form20_set))}): {sorted(set(int(y) for _,_,y in form20_set))}")
print(f"Years in AC-PC   ({len(set(int(y) for _,_,y in acpc_set))}): {sorted(set(int(y) for _,_,y in acpc_set))}")
print(f"\nBy type (Form20 / AC-PC):")
for t in all_types:
    f20 = type_f20.get(t,0); ac = type_acpc.get(t,0)
    p = round(f20/ac*100) if ac else 0
    print(f"  {t:6}: {f20:3}/{ac:3} = {p}%")
