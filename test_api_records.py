import urllib.request, json
req = urllib.request.Request("http://127.0.0.1:5050/api/records")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    print([d for d in data if d['state']=='AN' and d['el_year']==2009])
