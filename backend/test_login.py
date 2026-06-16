import httpx, json

BASE = "http://localhost:8000/api"

# Try login for each user with admin123
resp = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
print(f"admin/admin123: {resp.status_code} {resp.text[:100]}")

resp = httpx.post(f"{BASE}/auth/login", json={"username": "emp1", "password": "password123"}, timeout=10)
print(f"emp1/password123: {resp.status_code} {resp.text[:100]}")

resp = httpx.post(f"{BASE}/auth/login", json={"username": "emp1", "password": "admin123"}, timeout=10)
print(f"emp1/admin123: {resp.status_code} {resp.text[:100]}")

resp = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
print(f"admin (retry): {resp.status_code} {resp.text[:100]}")
