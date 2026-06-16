import urllib.request
import json

# Test emp1 login via API
data = json.dumps({"username": "emp1", "password": "emp1@0001"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/auth/login", data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=5)
    print("Login OK:", json.loads(resp.read())["access_token"][:30])
except urllib.error.HTTPError as e:
    print("Login failed:", e.read().decode())
