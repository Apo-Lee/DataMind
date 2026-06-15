"""DataMind Agent 端到端完整测试
用真实数据库、真实用户、真实 API 进行全链路测试"""
import asyncio, os, json, sys, uuid, time
from datetime import datetime, timezone

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
sys.path.insert(0, ".")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.models.user import User, UserRole, DataScope
from app.models.datasource import DataSource
from app.core.auth import get_current_user
from app.core.permissions import check_datasource_access, get_agent_with_rls
from app.agents.factory import agent_factory
from app.agents.intent import detect_intent
from app.agents.sql_agent import generate_sql
from app.core.query_engine import safe_query
from app.core.llm_client import llm_client
from app.orchestrator.nodes.intent_node import intent_node
from app.orchestrator.state import AgentContext


# ============================================================
# 测试配置
# ============================================================
TEST_USER_MAP = {
    "admin":        {"username": "admin",       "role": "admin",       "data_scope": "all",       "desc": "系统管理员"},
    "dept_ceo":     {"username": "emp1",        "role": "dept_ceo",    "data_scope": "team",      "desc": "技术研发中心负责人"},
    "dept_manager": {"username": "emp17",       "role": "dept_manager","data_scope": "team",      "desc": "前端开发部经理"},
    "employee":     {"username": "emp2",        "role": "employee",    "data_scope": "self_only", "desc": "普通员工"},
}

TEST_RESULTS = []


def record(test_id, user_label, question, passed, detail, sql="", error=""):
    """记录测试结果"""
    TEST_RESULTS.append({
        "id": test_id,
        "user": user_label,
        "question": question,
        "passed": passed,
        "detail": detail,
        "sql": sql[:300] if sql else "",
        "error": error,
    })


async def get_test_user(db, username):
    """获取测试用户"""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_datasource_by_tag(db, tag):
    """获取数据源"""
    result = await db.execute(
        select(DataSource).where(DataSource.business_tag == tag, DataSource.is_active == True)
    )
    return result.scalar_one_or_none()


async def test_sql_execution(db, user, ds, question, test_id, user_label):
    """测试 SQL 生成质量 — 重点检查 SQL 是否能实际执行"""
    try:
        agent, _ = await get_agent_with_rls(user, ds.id, db)
        agent._user_role = user.role.value if hasattr(user.role, "value") else user.role
        agent._user_data_scope = user.data_scope.value if hasattr(user.data_scope, "value") else user.data_scope
        agent._user_id = user.id
        agent._user_employee_id = user.employee_id
        agent._user_dept_id = user.dept_id

        user_info = {
            "role": agent._user_role,
            "data_scope": agent._user_data_scope,
            "employee_id": agent._user_employee_id,
            "dept_id": agent._user_dept_id,
        }

        # 先试结构化路径
        result = await safe_query(question, agent, user_info)

        if result.get("rejected"):
            record(test_id, user_label, question, True, f"安全拒绝: {result.get('error','')}", error=result.get("error",""))
            return

        sql = result.get("sql", "")
        df = result.get("data")
        error_msg = result.get("error", "")

        if df is not None and not df.empty:
            rows = len(df)
            cols = list(df.columns)
            record(test_id, user_label, question, True,
                   f"执行成功: {rows} 行, 列={cols}", sql=sql)
        elif df is not None and df.empty:
            record(test_id, user_label, question, True,
                   "执行成功: 0 行数据", sql=sql)
        else:
            record(test_id, user_label, question, False,
                   f"执行失败: {error_msg}", sql=sql, error=error_msg)

    except Exception as e:
        record(test_id, user_label, question, False,
               f"异常: {e}", error=str(e))


async def check_dept_columns(db, ds):
    """检查 departments 表和 employees 表的关系"""
    try:
        conn_url = f"sqlite:///../demo_data/hr_demo.sqlite"
        from sqlalchemy import create_engine
        engine = create_engine(conn_url)
        with engine.connect() as conn:
            # departments 表有哪些列
            result = conn.execute(text("PRAGMA table_info(departments)"))
            dept_cols = [row[1] for row in result.fetchall()]
            print(f"departments 列: {dept_cols}")

            # employees 表有哪些列
            result = conn.execute(text("PRAGMA table_info(employees)"))
            emp_cols = [row[1] for row in result.fetchall()]
            print(f"employees 列: {emp_cols}")

            # 看看两者的关系
            result = conn.execute(text("SELECT id, name FROM departments LIMIT 20"))
            print(f"departments 数据: {result.fetchall()}")
    except Exception as e:
        print(f"查询失败: {e}")


async def run_e2e_tests():
    """运行端到端测试"""

    print("=" * 80)
    print("DataMind Agent 端到端完整测试")
    print("=" * 80)

    # 初始化数据库连接
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    db = async_session()

    try:
        # 获取测试用户
        users = {}
        for label, info in TEST_USER_MAP.items():
            user = await get_test_user(db, info["username"])
            if user:
                users[label] = user
                print(f"  [OK] {label}: {info['desc']} (id={user.id[:8]}...)")
            else:
                print(f"  [ERR] {label} 用户不存在")

        # 获取 HR 数据源
        hr_ds = await get_datasource_by_tag(db, "hr")
        crm_ds = await get_datasource_by_tag(db, "crm")
        print(f"\n  HR 数据源: {hr_ds.name if hr_ds else 'None'}, id={hr_ds.id[:8] if hr_ds else 'N/A'}")
        print(f"  CRM 数据源: {crm_ds.name if crm_ds else 'None'}, id={crm_ds.id[:8] if crm_ds else 'N/A'}")

        if hr_ds:
            await check_dept_columns(db, hr_ds)

        print("\n" + "=" * 80)
        print("开始执行测试...")
        print("=" * 80)

        # ============================================================
        # 测试集 1: HR 场景 — 简单查询
        # ============================================================
        print("\n【测试集 1: HR 简单查询】")
        if hr_ds and users.get("dept_ceo"):
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "技术研发中心有多少员工", "HR-SQL-01", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "列出人力资源部的部门名称和预算", "HR-SQL-02", "dept_ceo")

        # ============================================================
        # 测试集 2: HR 场景 — 聚合统计
        # ============================================================
        print("\n【测试集 2: HR 聚合统计】")
        if hr_ds and users.get("dept_ceo"):
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "各部门的平均薪资是多少", "HR-AGG-01", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "员工的学历分布情况", "HR-AGG-02", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "每个部门的薪资总额排行", "HR-AGG-03", "dept_ceo")

        # ============================================================
        # 测试集 3: HR 场景 — 出勤率
        # ============================================================
        print("\n【测试集 3: HR 出勤率相关】")
        if hr_ds and users.get("dept_ceo"):
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "上个月各部门的出勤率是多少", "HR-ATT-01", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "近6个月出勤率变化趋势", "HR-ATT-02", "dept_ceo")
            await test_sql_execution(db, users["dept_manager"], hr_ds,
                "我们部门本月有多少人请假", "HR-ATT-03", "dept_manager")

        # ============================================================
        # 测试集 4: HR 场景 — 对比 & 排行
        # ============================================================
        print("\n【测试集 4: HR 对比 & 排行】")
        if hr_ds and users.get("dept_ceo"):
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "对比技术研发中心和市场营销部的平均绩效评分", "HR-CMP-01", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], hr_ds,
                "绩效评分最高的前10名员工", "HR-RNK-01", "dept_ceo")

        # ============================================================
        # 测试集 5: 权限边界
        # ============================================================
        print("\n【测试集 5: 权限边界测试】")
        if hr_ds and users.get("employee"):
            await test_sql_execution(db, users["employee"], hr_ds,
                "所有人的薪资是多少", "PERM-01", "employee")
            await test_sql_execution(db, users["employee"], hr_ds,
                "全公司的出勤率", "PERM-02", "employee")

        # ============================================================
        # 测试集 6: CRM 场景
        # ============================================================
        print("\n【测试集 6: CRM 场景】")
        if crm_ds and users.get("dept_ceo"):
            await test_sql_execution(db, users["dept_ceo"], crm_ds,
                "上个月的销售总额是多少", "CRM-01", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], crm_ds,
                "各行业的客户数量分布", "CRM-02", "dept_ceo")
            await test_sql_execution(db, users["dept_ceo"], crm_ds,
                "赢单率最高的销售团队", "CRM-03", "dept_ceo")

    finally:
        await db.close()
        await engine.dispose()

    # ============================================================
    # 输出结果
    # ============================================================
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)

    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    failed = sum(1 for r in TEST_RESULTS if not r["passed"])
    total = len(TEST_RESULTS)

    print(f"\n总用例: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/total*100:.0f}%\n" if total > 0 else "")

    # 失败的详细分析
    print("-" * 60)
    print("失败用例详情:")
    print("-" * 60)
    for r in TEST_RESULTS:
        if not r["passed"]:
            print(f"\n  [{r['id']}] {r['user']}: {r['question']}")
            print(f"    错误: {r['error']}")

    # 通过的 SQL 展示
    print("\n" + "-" * 60)
    print("通过的 SQL 展示:")
    print("-" * 60)
    for r in TEST_RESULTS:
        if r["passed"] and r["sql"]:
            print(f"\n  [{r['id']}] {r['user']}: {r['question']}")
            print(f"    结果: {r['detail']}")
            print(f"    SQL: {r['sql'][:200]}...")

    # 问题诊断
    print("\n" + "=" * 80)
    print("综合诊断")
    print("=" * 80)
    print(f"""
通过率: {passed}/{total} = {passed/total*100:.0f}%

{'所有测试通过!' if passed == total else f'发现 {failed} 个问题需要修复'}
""")


asyncio.run(run_e2e_tests())
