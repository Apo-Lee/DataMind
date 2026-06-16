import urllib.request, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def api_post(path, data, token=None):
    url = f"http://127.0.0.1:8000{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}

def get_token_for(username, pwd):
    r = api_post("/api/auth/login", {"username": username, "password": pwd})
    if "access_token" in r:
        return r["access_token"]
    print(f"  Login failed for {username}")
    return None

def get_datasources(token):
    url = "http://127.0.0.1:8000/api/datasources"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req, timeout=5)
    return json.loads(resp.read())

def ask(token, ds_id, question):
    return api_post("/api/query/ask", {"question": question, "datasource_id": ds_id}, token)

test_users = {
    "admin": ("admin", "admin123"),
    "emp1": ("emp1", "emp1@0001"),
    "emp2": ("emp2", "emp2@0002"),
    "emp31": ("emp31", "emp31@0031"),
}

questions = [
    ("hr", "各部门预算情况"),
    ("hr", "各部门人力分布如何"),
    ("hr", "我的个人信息"),
    ("hr", "绩效排名最高的员工"),
    ("finance", "本月费用支出概览"),
]

for uid, (uname, pwd) in test_users.items():
    print(f"\n{'='*60}")
    print(f"USER: {uname} ({uid})")
    token = get_token_for(uname, pwd)
    if not token:
        continue
    ds_list = get_datasources(token)
    for tag, q in questions:
        ds = next((d for d in ds_list if d["business_tag"] == tag), None)
        if not ds:
            print(f"  SKIP {tag}: no datasource found")
            continue
        print(f"\n  [{tag}] Q: {q}")
        resp = ask(token, ds["id"], q)
        if resp.get("error"):
            print(f"  ERROR: {resp['error']}")
            continue
        md = resp.get("report_markdown", "")
        lines = md.split("\n")
        print(f"  REPORT ({len(md)} chars):")
        for line in lines[:12]:
            print(f"    {line}")
        if len(lines) > 12:
            print(f"    ... ({len(lines)-12} more lines)")
        print()
