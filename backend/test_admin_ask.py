import httpx, json

BASE = "http://localhost:8000/api"

# 用 admin 登录
resp = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
admin_token = resp.json()["access_token"]
print(f"Admin token: {admin_token[:30]}...")

headers = {"Authorization": f"Bearer {admin_token}"}

# 获取数据源
resp = httpx.get(f"{BASE}/datasources", headers=headers, timeout=10)
dss = resp.json()

hr_ds = None
crm_ds = None
for ds in dss:
    if isinstance(ds, dict):
        if ds.get("business_tag") == "hr":
            hr_ds = ds["id"]
        if ds.get("business_tag") == "crm":
            crm_ds = ds["id"]

print(f"HR datasource: {hr_ds}")
print(f"CRM datasource: {crm_ds}")

# 用 admin token 直接问问题（admin 有最高权限）
resp = httpx.post(f"{BASE}/query/ask", json={
    "datasource_id": hr_ds,
    "question": "技术研发中心有多少员工"
}, headers=headers, timeout=30)
data = resp.json()
print(f"\n[admin] 技术研发中心有多少员工")
print(f"  status: {resp.status_code}")
print(f"  intent: {data.get('intent', '?')}")
print(f"  sql: {data.get('sql_generated', '')[:150]}")
insights = data.get("insights", [])
if insights:
    for ins in insights[:2]:
        print(f"  insight: {str(ins.get('content',''))[:80]}")
