"""DataMind Agent 经典角色端到端测试

模拟 7 个真实业务角色的完整查询场景。
每个角色模拟不同的数据权限和数据范围。
"""
import sys; sys.path.insert(0, "E:\\Python_Code_Project\\DataMind\\backend")
import asyncio, json, os
os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

from sqlalchemy import create_engine, text
from app.database import init_db, async_session
from app.models.user import User, UserRole, DataScope
from app.models.datasource import DataSource
from sqlalchemy import select

# ============================================================
# 角色定义
# ============================================================
ROLES = {
    "admin": {
        "desc": "系统管理员 — 可查看全部4个数据源的所有数据",
        "username": "admin", "password": "admin123",
        "role": "admin", "data_scope": "all",
        "employee_id": None, "dept_id": None,
    },
    "dept_ceo": {
        "desc": "张伟(技术总监) — 看技术研发中心及子部门(101/102/103)",
        "username": "emp1", "password": "emp1@0001",
        "role": "dept_ceo", "data_scope": "team",
        "employee_id": 1, "dept_id": 1,
    },
    "dept_manager": {
        "desc": "沈洁(产品研发经理) — 看产品研发部(dept=102)的团队数据",
        "username": "emp17", "password": "emp17@0017",
        "role": "dept_manager", "data_scope": "team",
        "employee_id": 17, "dept_id": 102,
    },
    "hr_director": {
        "desc": "王静(HR总监) — 看全公司HR相关数据(dept_and_sub)",
        "username": "emp68", "password": "emp68@0068",
        "role": "hr_director", "data_scope": "dept_and_sub",
        "employee_id": 68, "dept_id": 3,
    },
    "finance_director": {
        "desc": "赵刚(财务总监) — 看全公司财务数据(all)",
        "username": "emp80", "password": "emp80@0080",
        "role": "finance_director", "data_scope": "all",
        "employee_id": 80, "dept_id": 4,
    },
    "sales_manager": {
        "desc": "任飞(华东区域经理) — 看华东大区(dept=501)的销售数据",
        "username": "emp104", "password": "emp104@0104",
        "role": "sales_manager", "data_scope": "team",
        "employee_id": 104, "dept_id": 501,
    },
    "employee": {
        "desc": "普通员工(平台架构部) — 仅看自己的数据",
        "username": "emp2", "password": "emp2@0002",
        "role": "employee", "data_scope": "self_only",
        "employee_id": 2, "dept_id": 101,
    },
}


# ============================================================
# 测试查询定义
# ============================================================
QUERIES = {
    "admin": [
        ("HR-计数", "hr", "公司总共有多少员工", None),
        ("HR-聚合", "hr", "各部门的平均绩效评分排名", None),
        ("HR-薪资", "hr", "全公司的薪资分布情况", None),
        ("CRM-交易", "crm", "今年成交的销售总额", None),
        ("CRM-排行", "crm", "成交金额最高的前10个客户", None),
        ("CRM-跟进", "crm", "最近一个月的客户跟进记录", None),
        ("Finance-预算", "finance", "各部门的预算执行情况", None),
        ("Finance-费用", "finance", "近3个月的月度费用趋势", None),
        ("ERP-项目", "erp", "所有进行中的项目", None),
        ("ERP-库存", "erp", "库存数量低于安全库存的物料", None),
    ],
    "dept_ceo": [
        ("部门人数", "hr", "技术研发中心有多少员工", None),
        ("团队绩效", "hr", "我部门员工的绩效评分排名", None),
        ("考勤情况", "hr", "上个月的部门出勤率", None),
        ("学历分布", "hr", "我部门员工的学历分布", None),
    ],
    "dept_manager": [
        ("团队人数", "hr", "产品研发部有多少人", None),
        ("团队绩效", "hr", "我的团队成员绩效评分", None),
        ("考勤统计", "hr", "本月产品研发部的出勤情况", None),
        ("薪资拒绝", "hr", "查看所有员工的薪资", "rejected"),
    ],
    "hr_director": [
        ("全司人数", "hr", "公司总共有多少在职员工", None),
        ("部门人数", "hr", "统计各部门的在职人数", None),
        ("绩效分布", "hr", "全公司员工的绩效评分分布", None),
        ("薪资分析", "hr", "各部门的平均薪资对比", None),
        ("考勤趋势", "hr", "近6个月的出勤趋势", None),
    ],
    "finance_director": [
        ("部门预算", "finance", "各部门今年的预算和已使用金额", None),
        ("费用趋势", "finance", "近3个月各月的费用总额", None),
        ("费用类别", "finance", "按类别统计费用总额", None),
    ],
    "sales_manager": [
        ("团队业绩", "crm", "我团队今年的销售目标完成情况", None),
        ("客户列表", "crm", "我团队负责的客户有哪些", None),
        ("交易排行", "crm", "我团队的成交金额Top 5", None),
    ],
    "employee": [
        ("个人信息", "hr", "我的个人信息", None),
        ("我的考勤", "hr", "我这个月的出勤记录", None),
        ("我的绩效", "hr", "我的绩效评分", None),
        ("查薪资", "hr", "所有人的薪资", "rejected"),
        ("全员统计", "hr", "全公司平均出勤率", "rejected"),
    ],
}

# 真实数据库引擎
ENGINES = {
    "hr": create_engine("sqlite:///../demo_data/hr_demo.sqlite"),
    "crm": create_engine("sqlite:///../demo_data/crm_demo.sqlite"),
    "finance": create_engine("sqlite:///../demo_data/finance_demo.sqlite"),
    "erp": create_engine("sqlite:///../demo_data/erp_demo.sqlite"),
}


def verify_sql(sql: str, business_tag: str) -> dict:
    """在真实数据库上验证 SQL"""
    if not sql:
        return {"ok": False, "error": "SQL为空"}
    engine = ENGINES.get(business_tag)
    if not engine:
        return {"ok": False, "error": f"未知数据源: {business_tag}"}
    sql_upper = sql.upper()
    errors = []
    if not sql_upper.strip().startswith("SELECT"):
        errors.append("不是SELECT语句")
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT"]
    for kw in dangerous:
        if kw in sql_upper:
            errors.append(f"危险操作: {kw}")
    if errors:
        return {"ok": False, "error": "; ".join(errors)}
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            return {"ok": True, "rows": len(rows), "columns": list(result.keys()) if rows else []}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def run_test():
    await init_db()
    async with async_session() as session:
        dss = {ds.business_tag: ds for ds in (await session.execute(select(DataSource))).scalars().all()}

    print("=" * 80)
    print("DataMind Agent 经典角色端到端测试")
    print("=" * 80)

    stats = {"pass": 0, "fail": 0, "reject": 0}

    for role_key, role_info in ROLES.items():
        queries = QUERIES.get(role_key, [])
        if not queries:
            continue

        print(f"\n--- [{role_key}] {role_info['desc']}")

        from app.core.permissions import get_agent_with_rls
        from app.core.query_engine import safe_query

        class MockUser:
            def __init__(self, info):
                self.id = f"mock-{role_key}"
                self.username = info["username"]
                self.role = UserRole(info["role"])
                self.data_scope = DataScope(info["data_scope"])
                self.employee_id = info["employee_id"]
                self.dept_id = info["dept_id"]
                self.dept_name = ""
                self.extra_dept_ids = None
                self.display_name = f"Mock-{role_key}"
                self.is_active = True

        user = MockUser(role_info)

        for qname, ds_tag, question, expected in queries:
            ds = dss.get(ds_tag)
            if not ds:
                print(f"  [SKIP] {qname}: 数据源 {ds_tag} 不存在")
                continue

            try:
                agent, _ = await get_agent_with_rls(user, ds.id, session)
                agent._user_role = role_info["role"]
                agent._user_data_scope = role_info["data_scope"]
                agent._user_employee_id = role_info["employee_id"]
                agent._user_dept_id = role_info["dept_id"]

                result = await safe_query(question, agent, {
                    "role": role_info["role"],
                    "data_scope": role_info["data_scope"],
                    "employee_id": role_info["employee_id"],
                    "dept_id": role_info["dept_id"],
                })

                if result.get("rejected"):
                    err = result.get("error", "")
                    if expected == "rejected":
                        print(f"  [OK-reject] {qname}: {err}")
                        stats["reject"] += 1
                    else:
                        print(f"  [FAIL] {qname}: 不应拒绝但被拒绝 => {err}")
                        stats["fail"] += 1
                    continue

                sql = result.get("sql", "")
                if not sql:
                    print(f"  [FAIL] {qname}: SQL为空")
                    stats["fail"] += 1
                    continue

                ver = verify_sql(sql, ds_tag)
                if ver["ok"]:
                    print(f"  [PASS] {qname}: {ver['rows']}行 {ver['columns']}")
                    stats["pass"] += 1
                else:
                    print(f"  [FAIL] {qname}: SQL执行失败 => {ver['error']}")
                    print(f"         SQL: {sql[:150]}")
                    stats["fail"] += 1

            except Exception as e:
                print(f"  [FAIL] {qname}: 异常 => {e}")
                stats["fail"] += 1

        await asyncio.sleep(0)

    # 汇总
    print(f"\n{'=' * 80}")
    print(f"汇总: 通过={stats['pass']}  失败={stats['fail']}  按预期拒绝={stats['reject']}")
    total = stats["pass"] + stats["fail"] + stats["reject"]
    print(f"总用例: {total}")
    safe_total = total - stats["reject"]
    if safe_total > 0:
        print(f"SQL可执行率: {stats['pass']}/{safe_total} = {stats['pass']/safe_total*100:.0f}%")
    print()

asyncio.run(run_test())
