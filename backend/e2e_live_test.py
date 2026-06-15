import os, json, httpx, asyncio
import time

BASE = "http://localhost:8000/api"

# ============================================================
# 测试账号
# ============================================================
USERS = {
    "张伟-技术总监": {
        "username": "emp1", "password": "password123",
        "role": "dept_ceo", "dept": "技术研发中心(部门1)",
        "desc": "部门CEO，可查看本部门及下属部门"
    },
    "沈洁-部门经理": {
        "username": "emp17", "password": "password123",
        "role": "dept_manager", "dept": "前端开发部(部门102)",
        "desc": "部门经理，可查看本部门数据"
    },
    "孙明-普通员工": {
        "username": "emp2", "password": "password123",
        "role": "employee", "dept": "平台架构部(部门101)",
        "desc": "普通员工，只能查看自己数据"
    },
}

# 测试问题（按角色分配）
QUESTIONS = {
    "张伟-技术总监": [
        # 简单查询
        ("S1", "技术研发中心有多少员工", "简单计数"),
        ("S2", "列出人力资源部的预算是多少", "部门预算查询"),
        # 聚合
        ("A1", "各部门的平均薪资是多少", "平均薪资"),
        ("A2", "员工的学历分布情况", "学历分布"),
        # 出勤
        ("AT1", "上个月各部门的出勤率是多少", "出勤率"),
        ("AT2", "近6个月出勤率变化趋势", "出勤率趋势"),
        # 排行
        ("R1", "绩效评分最高的前10名员工", "绩效排行"),
        # 对比
        ("C1", "对比技术研发中心和市场营销部的平均绩效评分", "部门对比"),
    ],
    "沈洁-部门经理": [
        ("M1", "我们部门有多少人", "部门人数"),
        ("M2", "我们部门本月有多少人请假", "请假人数"),
        ("M3", "我们部门的平均绩效评分是多少", "部门绩效"),
    ],
    "孙明-普通员工": [
        ("E1", "我这个月的出勤情况怎么样", "个人出勤"),
        ("E2", "我的绩效评分是多少", "个人绩效"),
        # 下面这些应该被拒绝
        ("E3", "所有人的薪资是多少", "越权查询(应拒绝)"),
        ("E4", "全公司的出勤率", "越权聚合(应拒绝)"),
    ],
}


async def login(client, username, password):
    """登录获取 token"""
    resp = await client.post(f"{BASE}/auth/login", json={
        "username": username, "password": password
    })
    return resp.json()


async def ask(client, token, datasource_id, question):
    """向 Agent 提问"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"{BASE}/query/ask", json={
        "datasource_id": datasource_id,
        "question": question,
    }, headers=headers)
    return resp


async def run_tests():
    client = httpx.AsyncClient(timeout=60)
    
    # 先登录获取所有 token
    tokens = {}
    for name, info in USERS.items():
        resp = await login(client, info["username"], info["password"])
        if "access_token" in resp:
            tokens[name] = resp["access_token"]
            print(f"[LOGIN] {name} -> OK")
        elif "detail" in resp:
            # 可能密码不一样
            resp2 = await login(client, info["username"], "123456")
            if "access_token" in resp2:
                tokens[name] = resp2["access_token"]
                print(f"[LOGIN] {name} -> OK (123456)")
            else:
                print(f"[LOGIN] {name} -> FAIL: {resp}")
    
    if not tokens:
        print("NO TOKENS! Trying direct login with emp1...")
        resp = await login(client, "emp1", "123456")
        print(f"emp1 login: {resp}")
        
    # 获取数据源 ID
    admin_token = tokens.get("张伟-技术总监", list(tokens.values())[0] if tokens else "")
    if admin_token:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get(f"{BASE}/datasources", headers=headers)
        datasources = resp.json()
        print(f"\nDataSources: {json.dumps(datasources[:2], ensure_ascii=False, indent=2)}")
        
        hr_ds_id = None
        crm_ds_id = None
        for ds in datasources:
            if isinstance(ds, dict):
                if ds.get("business_tag") == "hr":
                    hr_ds_id = ds["id"]
                if ds.get("business_tag") == "crm":
                    crm_ds_id = ds["id"]
        
        print(f"HR datasource: {hr_ds_id}")
    
    print("\n" + "=" * 80)
    print("开始端到端测试...")
    print("=" * 80)
    
    results = []
    
    for name, questions in QUESTIONS.items():
        token = tokens.get(name)
        if not token:
            print(f"\n[SKIP] {name}: no token")
            continue
        
        print(f"\n{'='*60}")
        print(f"用户: {name} ({USERS[name]['role']})")
        print(f"说明: {USERS[name]['desc']}")
        print(f"{'='*60}")
        
        for test_id, question, category in questions:
            print(f"\n  [{test_id}] ({category})")
            print(f"  问题: {question}")
            
            try:
                resp = await ask(client, token, hr_ds_id, question)
                status_code = resp.status_code
                data = resp.json()
                
                if status_code == 200:
                    intent = data.get("intent", "?")
                    sql = data.get("sql_generated", "")
                    insights = data.get("insights", [])
                    report = data.get("report_markdown", "")
                    
                    # 检查是否有错误信息
                    if "detail" in data:
                        print(f"  结果: 拒绝 - {data['detail'][:100]}")
                        results.append((test_id, "REJECTED", data["detail"]))
                    else:
                        print(f"  意图: {intent}")
                        if sql:
                            print(f"  SQL: {sql[:120]}...")
                        if insights:
                            for ins in insights[:2]:
                                print(f"  洞察: {str(ins.get('content',''))[:80]}")
                        if report:
                            print(f"  报告: {report[:100]}...")
                        results.append((test_id, "OK", sql[:80] if sql else "no sql"))
                else:
                    detail = data.get("detail", str(data))
                    print(f"  结果: 错误({status_code}) - {detail[:100]}")
                    results.append((test_id, f"ERROR {status_code}", detail[:80]))
                    
            except Exception as e:
                print(f"  结果: 异常 - {e}")
                results.append((test_id, "EXCEPTION", str(e)[:60]))
    
    # 汇总
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    
    ok_count = sum(1 for r in results if r[1] == "OK")
    rej_count = sum(1 for r in results if r[1] == "REJECTED")
    err_count = sum(1 for r in results if r[1].startswith("ERROR") or r[1] == "EXCEPTION")
    
    print(f"\n总用例: {len(results)}")
    print(f"通过(OK): {ok_count}")
    print(f"拒绝(预期): {rej_count}")
    print(f"错误: {err_count}")
    print(f"SQL可执行率(OK): {ok_count}/{len(results)} = {ok_count/len(results)*100:.0f}%" if results else "")
    
    for r in results:
        if r[1].startswith("ERROR") or r[1] == "EXCEPTION":
            print(f"  [FAIL] {r[0]}: {r[2]}")
    
    await client.aclose()


asyncio.run(run_tests())
