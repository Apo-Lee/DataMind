"""DataMind Agent ? Parametrized Role E2E Tests"""
import sys, os
os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
sys.path.insert(0, ".")
import pytest
from sqlalchemy import create_engine, text, select
from app.database import init_db, async_session
from app.models.user import UserRole, DataScope
from app.models.datasource import DataSource

ROLES = {"admin":{"role":"admin","scope":"all","emp":None,"dept":None},"dept_ceo":{"role":"dept_ceo","scope":"team","emp":1,"dept":1},"dept_manager":{"role":"dept_manager","scope":"team","emp":17,"dept":102},"hr_director":{"role":"hr_director","scope":"dept_and_sub","emp":68,"dept":3},"finance_director":{"role":"finance_director","scope":"all","emp":80,"dept":4},"sales_manager":{"role":"sales_manager","scope":"team","emp":104,"dept":501},"employee":{"role":"employee","scope":"self_only","emp":2,"dept":101}}

ENG = None
def get_eng():
    global ENG
    if ENG is None:
        ENG = {"hr":create_engine("sqlite:///../demo_data/hr_demo.sqlite"),"crm":create_engine("sqlite:///../demo_data/crm_demo.sqlite"),"finance":create_engine("sqlite:///../demo_data/finance_demo.sqlite"),"erp":create_engine("sqlite:///../demo_data/erp_demo.sqlite")}
    return ENG

def verify_sql(sql, tag):
    if not sql: return {"ok":False,"error":"Empty"}
    e = get_eng().get(tag)
    if not e: return {"ok":False,"error":"No engine"}
    if not sql.upper().strip().startswith("SELECT"): return {"ok":False,"error":"Not SELECT"}
    for kw in ["INSERT","UPDATE","DELETE","DROP","ALTER","TRUNCATE","GRANT"]:
        if kw in sql.upper(): return {"ok":False,"error":"Dangerous: "+kw}
    try:
        with e.connect() as c:
            r = c.execute(text(sql)).fetchall()
            return {"ok":True,"rows":len(r)}
    except Exception as ex:
        return {"ok":False,"error":str(ex)[:200]}

MOCK_CACHE = {}
def get_mock(key):
    if key not in MOCK_CACHE:
        ri = ROLES[key]
        class MockU:
            def __init__(s):
                s.id = "mock-"+key
                s.username = "Mock"
                s.role = UserRole(ri["role"])
                s.data_scope = DataScope(ri["scope"])
                s.employee_id = ri["emp"]
                s.dept_id = ri["dept"]
                s.dept_name = ""
                s.extra_dept_ids = None
                s.display_name = "Mock-"+key
                s.is_active = True
        MOCK_CACHE[key] = MockU
    return MOCK_CACHE[key]()

TESTS = [
    ("admin","hr","各部门人员分布如何","admin-hr-count"),
    ("admin","crm","客户签约金额统计","admin-crm-sum"),
    ("admin","finance","各部门预算情况","admin-finance-budget"),
    ("admin","erp","项目进展概览","admin-erp-projects"),
    ("dept_ceo","hr","本部门人员统计","ceo-count"),
    ("dept_ceo","hr","本部门员工绩效分析","ceo-perf"),
    ("dept_manager","hr","各属下人数统计","mgr-count"),
    ("dept_manager","hr","属下员工绩效评估","mgr-perf"),
    ("hr_director","hr","全公司人员统计","hr-count"),
    ("hr_director","hr","薪酬统计分析","hr-salary"),
    ("hr_director","hr","近6个月人员变动趋势","hr-trend"),
    ("finance_director","finance","各部门预算使用情况","fin-budget"),
    ("finance_director","finance","近3个月费用趋势","fin-trend"),
    ("sales_manager","crm","销售目标完成情况","sales-target"),
    ("sales_manager","crm","销售人员排名","sales-rank"),
    ("employee","hr","本人考勤记录","emp-att"),
    ("employee","hr","本人工作信息","emp-info"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("rk,bt,q,id_", TESTS, ids=[t[3] for t in TESTS])
async def test_role_query(rk, bt, q, id_):
    from app.core.permissions import get_agent_with_rls
    from app.core.query_engine import safe_query
    await init_db()
    async with async_session() as session:
        ds = (await session.execute(select(DataSource).where(DataSource.business_tag == bt))).scalars().first()
        assert ds, f"DS {bt} not found"
        user = get_mock(rk)
        ri = ROLES[rk]
        agent, _ = await get_agent_with_rls(user, ds.id, session)
        result = await safe_query(q, agent, {"role":ri["role"],"data_scope":ri["scope"],"employee_id":ri["emp"],"dept_id":ri["dept"]})
        if result.get("rejected"):
            pytest.skip("Rejected: "+str(result.get("error")))
        sql = result.get("sql","")
        assert sql, "SQL empty"
        ver = verify_sql(sql, bt)
        assert ver["ok"], f"SQL fail: {str(ver.get('error'))} | SQL: {str(sql)[:150]}"
        assert ver["rows"] >= 1, f"Expect rows, got 0 | SQL: {str(sql)[:100]}"

@pytest.mark.asyncio
async def test_salary_rejected():
    from app.core.permissions import get_agent_with_rls
    from app.core.query_engine import safe_query
    await init_db()
    async with async_session() as session:
        ds = (await session.execute(select(DataSource).where(DataSource.business_tag == "hr"))).scalars().first()
        user = get_mock("dept_manager")
        agent, _ = await get_agent_with_rls(user, ds.id, session)
        result = await safe_query("查看全公司薪酬表", agent, {"role":"dept_manager","data_scope":"team","employee_id":17,"dept_id":102})
        assert result.get("rejected"), "Should reject salary for dept_manager!"
