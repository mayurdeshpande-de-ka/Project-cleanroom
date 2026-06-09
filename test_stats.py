import urllib.request
import json

req = urllib.request.Request("http://127.0.0.1:5050/api/stats")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    print(json.dumps(data, indent=2))
