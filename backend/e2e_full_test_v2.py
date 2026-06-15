import os, sys, json, asyncio
os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
sys.path.insert(0, ".")

from sqlalchemy import select, text
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.models.user import User
from app.models.datasource import DataSource
from app.core.permissions import get_agent_with_rls
from app.core.query_engine import safe_query, SQLBuilder
from app.core.query_rewriter import QueryInterceptor

# 真实 HR 数据库引擎
hr_engine = create_engine("sqlite:///../demo_data/hr_demo.sqlite")

# ============================================================
# 改进的 MockUser — 支持所有属性
# ============================================================
class MockUser:
    """完整模拟 User 对象的所有属性"""
    def __init__(self, role, data_scope, employee_id, dept_id, user_id="mock-id"):
        self.id = user_id
        self.role = role
        self.data_scope = data_scope
        self.employee_id = employee_id
        self.dept_id = dept_id
        self.dept_name = ""
        self.extra_dept_ids = None  # 关键缺失属性
        self.display_name = f"Mock-{role}"

# ============================================================
# Mock 意图
# ============================================================
MOCK_INTENTS = {
    "技术研发中心有多少员工": {
        "question_type": "count", "main_table": "employees", "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "id", "alias": "cnt"}],
        "filters": [{"column": "status", "op": "=", "value": "在职"}],
        "group_by": [], "order_by": [], "limit": 10,
    },
    "各部门的平均薪资是多少": {
        "question_type": "aggregation", "main_table": "employees", "join_tables": ["departments"],
        "select_columns": [],
        "aggregations": [{"type": "AVG", "column": "salary", "alias": "avg_salary"}],
        "filters": [], "group_by": ["dept_id"], "order_by": [{"column": "avg_salary", "direction": "DESC"}], "limit": 100,
    },
    "员工的学历分布情况": {
        "question_type": "aggregation", "main_table": "employees", "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "id", "alias": "count"}],
        "filters": [], "group_by": ["education"], "order_by": [], "limit": 100,
    },
    "绩效评分最高的前10名员工": {
        "question_type": "ranking", "main_table": "employees", "join_tables": [],
        "select_columns": ["name", "performance_score"],
        "aggregations": [], "filters": [],
        "group_by": [], "order_by": [{"column": "performance_score", "direction": "DESC"}], "limit": 10,
    },
    "上个月各部门的出勤率是多少": {
        "question_type": "aggregation", "main_table": "attendance",
        "join_tables": ["employees", "departments"],
        "select_columns": [],
        "aggregations": [
            {"type": "COUNT", "column": "id", "alias": "total"},
            {"type": "SUM", "column": None, "alias": "normal_count"},
        ],
        "filters": [{"column": "date", "op": "BETWEEN", "value": ["2026-01-01", "2026-01-31"]}],
        "group_by": ["dept_id"], "order_by": [], "limit": 100,
    },
    "本部门本月有多少人请假": {
        "question_type": "count", "main_table": "attendance", "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "employee_id", "alias": "leave_count"}],
        "filters": [{"column": "status", "op": "=", "value": "请假"}],
        "group_by": [], "order_by": [], "limit": 100,
    },
    "本月出勤情况": {
        "question_type": "list", "main_table": "attendance", "join_tables": [],
        "select_columns": ["employee_id", "date", "status"],
        "aggregations": [],
        "filters": [{"column": "date", "op": "BETWEEN", "value": ["2026-01-01", "2026-01-31"]}],
        "group_by": [], "order_by": [], "limit": 100,
    },
    "所有人的薪资是多少": {
        "question_type": "list", "main_table": "employees", "join_tables": [],
        "select_columns": ["name", "salary"],
        "aggregations": [], "filters": [],
        "group_by": [], "order_by": [], "limit": 100,
    },
    "全公司的出勤率": {
        "question_type": "aggregation", "main_table": "attendance", "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "id", "alias": "total"}, {"type": "SUM", "column": None, "alias": "normal"}],
        "filters": [], "group_by": [], "order_by": [], "limit": 100,
    },
}

# 注入 mock intent
import app.core.query_engine as qe
original_parse = qe.parse_query_intent

async def mock_parse(question, agent):
    for key, val in MOCK_INTENTS.items():
        if key in question or question in key:
            return val
    return {"question_type": "list", "main_table": "employees", "select_columns": ["name"],
            "aggregations": [], "filters": [], "group_by": [], "order_by": [], "limit": 10, "join_tables": []}

qe.parse_query_intent = mock_parse


def verify_sql(sql):
    """在真实 SQLite 上执行并验证"""
    if not sql:
        return {"ok": False, "errors": ["SQL为空"], "rows": 0}
    sql_upper = sql.upper()
    errors = []
    if not sql_upper.strip().startswith("SELECT"):
        errors.append("不是SELECT语句")
    for kw in ["INSERT","UPDATE","DELETE","DROP","ALTER","TRUNCATE","CREATE"]:
        if kw in sql_upper: errors.append(f"危险操作: {kw}")
    if "departments" in sql.lower():
        for bc in ['"dept_id"', '"department_id"']:
            if bc in sql: errors.append(f"departments表无{bc}")
    try:
        with hr_engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            return {"ok": len(errors)==0, "errors": errors, "rows": len(rows), "columns": list(result.keys()) if rows else []}
    except Exception as e:
        errors.append(str(e)[:200])
        return {"ok": False, "errors": errors, "rows": 0}


async def run():
    print("=" * 80)
    print("DataMind Agent 全链路测试 (V3修复验证)")
    print("=" * 80)

    engine = create_async_engine(settings.database_url)
    session = async_sessionmaker(engine, class_=AsyncSession)()
    ds_result = await session.execute(select(DataSource).where(DataSource.business_tag=="hr", DataSource.is_active==True))
    hr_ds = ds_result.scalar_one_or_none()

    test_cases = [
        # (key, role, data_scope, dept_id, emp_id, question, expect)
        ("dept_ceo_S1", "dept_ceo", "dept", 1, 1, "技术研发中心有多少员工", "ok"),
        ("dept_ceo_A1", "dept_ceo", "dept", 1, 1, "各部门的平均薪资是多少", "ok"),
        ("dept_ceo_A2", "dept_ceo", "dept", 1, 1, "员工的学历分布情况", "ok"),
        ("dept_ceo_R1", "dept_ceo", "dept", 1, 1, "绩效评分最高的前10名员工", "ok"),
        ("dept_ceo_AT1", "dept_ceo", "dept", 1, 1, "上个月各部门的出勤率是多少", "ok"),
        ("dept_mgr_M1", "dept_manager", "team", 102, 17, "本部门本月有多少人请假", "ok"),
        ("emp_E1", "employee", "self_only", 101, 2, "本月出勤情况", "ok"),
        ("emp_P1", "employee", "self_only", 101, 2, "所有人的薪资是多少", "reject"),
        ("emp_P2", "employee", "self_only", 101, 2, "全公司的出勤率", "reject"),
    ]

    results = []
    for tid, role, ds, dept_id, emp_id, question, expect in test_cases:
        user = MockUser(role, ds, emp_id, dept_id, tid)
        print(f"\n[{tid}] {role:15s} dept={dept_id} emp={emp_id}")
        print(f"  问题: {question}")

        try:
            agent, _ = await get_agent_with_rls(user, hr_ds.id, session)
            agent._user_role = user.role
            agent._user_data_scope = user.data_scope
            agent._user_id = user.id
            agent._user_employee_id = user.employee_id
            agent._user_dept_id = user.dept_id
            agent._user_dept_name = ""

            result = await safe_query(question, agent, {
                "role": user.role, "data_scope": user.data_scope,
                "employee_id": user.employee_id, "dept_id": user.dept_id,
            })

            if result.get("rejected"):
                err = result.get("error","")
                print(f"  结果: ⛔ 拒绝 - {err}")
                results.append((tid, "rejected", err[:60], ""))
                continue

            sql = result.get("sql","")
            ver = verify_sql(sql)
            if ver["ok"]:
                print(f"  结果: ✅ {ver['rows']}行 列={ver['columns']}")
                print(f"  SQL: {sql[:180]}")
                results.append((tid, f"ok({ver['rows']}行)", "", sql[:100]))
            else:
                print(f"  结果: ❌ {'; '.join(ver['errors'])}")
                print(f"  SQL: {sql[:180]}")
                results.append((tid, "sql_error", "; ".join(ver['errors']), sql[:80]))
        except Exception as e:
            print(f"  结果: ❌ {e}")
            results.append((tid, "exception", str(e)[:80], ""))

    # 汇总
    print("\n" + "=" * 80)
    print("汇总")
    print("=" * 80)
    ok = sum(1 for r in results if r[1].startswith("ok"))
    rej = sum(1 for r in results if r[1]=="rejected")
    err = sum(1 for r in results if r[1] not in ("ok","rejected"))
    total = len(results)
    print(f"\n总: {total}  通过: {ok}  拒绝: {rej}  错误: {err}")
    print(f"SQL可执行率: {ok}/{total-err} = {ok/(total-err)*100:.0f}%")
    print()
    for r in results:
        icon = "✅" if r[1].startswith("ok") else "⛔" if r[1]=="rejected" else "❌"
        print(f"  {icon} {r[0]} -> {r[1]:15s}  {r[3][:80]}")

    # 恢复
    qe.parse_query_intent = original_parse
    await session.close()
    await engine.dispose()


asyncio.run(run())
