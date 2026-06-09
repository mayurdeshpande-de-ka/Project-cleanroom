import urllib.request, json
req = urllib.request.Request("http://127.0.0.1:5050/api/records?status=nondownloaded")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    print("Non-downloaded count:", len(data))
    statuses = set(d['overall_status'] for d in data)
    print("Statuses present:", statuses)
