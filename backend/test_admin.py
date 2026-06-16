import httpx, json

BASE = "http://localhost:8000/api"

resp = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
admin_token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {admin_token}"}

# First try: get datasources list to confirm
resp = httpx.get(f"{BASE}/datasources", headers=headers, timeout=10)
print(f"datasources: {resp.status_code}")
data = resp.json()
if isinstance(data, list):
    for ds in data:
        print(f"  {ds['id'][:12]}... name={ds['name']}, tag={ds['business_tag']}")
elif isinstance(data, dict):
    print(f"  {json.dumps(data, ensure_ascii=False)[:300]}")

# HR id from previous test
hr_id = "982a161a-945a-4c59-b6ce-7fd374e97967"

# Try ask with full error detail
resp = httpx.post(f"{BASE}/query/ask", json={
    "datasource_id": hr_id,
    "question": "技术部有多少员工"
}, headers=headers, timeout=30)
print(f"\nask: {resp.status_code}")
print(resp.text[:500])
