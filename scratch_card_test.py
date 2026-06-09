import json, os

LIVE_JSON_PATH = 'live_extracted.json'
AC_PC_JSON_PATH = 'ac_pc_extracted.json'

form20_set = set()
if os.path.exists(LIVE_JSON_PATH):
    with open(LIVE_JSON_PATH, encoding='utf-8') as f:
        for item in json.load(f):
            s, t, y = item.get('state','').strip(), item.get('el_type','').strip(), item.get('el_year','').strip()
            if s and t and y and '-BP' not in t:
                form20_set.add((s,t,y))

acpc_set = set()
if os.path.exists(AC_PC_JSON_PATH):
    with open(AC_PC_JSON_PATH, encoding='utf-8') as f:
        for item in json.load(f):
            s, t, y = item.get('state','').strip(), item.get('el_type','').strip(), item.get('el_year','').strip()
            if s and t and y and '-BP' not in t:
                acpc_set.add((s,t,y))

from collections import Counter
type_f20   = Counter(t for _,t,_ in form20_set)
type_acpc  = Counter(t for _,t,_ in acpc_set)
all_types  = sorted(set(list(type_f20)+list(type_acpc)))

print(f"Form 20 entries (non-BP):    {len(form20_set)}")
print(f"AC-PC mapping entries (non-BP): {len(acpc_set)}")
pct = round(len(form20_set)/len(acpc_set)*100) if acpc_set else 0
print(f"Coverage: {pct}%")
print(f"Remaining: {len(acpc_set)-len(form20_set)}")
print(f"\nYears in Form 20: {sorted(set(int(y) for _,_,y in form20_set))}")
print(f"Years in AC-PC:   {sorted(set(int(y) for _,_,y in acpc_set))}")
print(f"\nBy type:")
for t in all_types:
    f20 = type_f20.get(t,0); ac = type_acpc.get(t,0)
    p = round(f20/ac*100) if ac else 0
    print(f"  {t}: {f20}/{ac} = {p}%")
