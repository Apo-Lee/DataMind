# -*- coding: utf-8 -*-
"""
DataMind Agent E2E 测试 —— 直接模拟 Orchestrator 全流程
走 Intent Node + SQL Agent + Report Node 完整链路
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
os.chdir("E:/Python_Code_Project/DataMind/backend")

from app.database import init_db, async_session
from app.models.user import User, UserRole, DataScope
from app.models.datasource import DataSource
from app.agents.factory import agent_factory
from sqlalchemy import select
from app.orchestrator.state import AgentContext, route_by_intent, route_after_sql
from app.orchestrator.nodes.intent_node import intent_node
from app.orchestrator.nodes.report_node import report_node
from app.core.row_level_security import RowLevelSecurityEngine
from app.core.query_engine import safe_query
from datetime import datetime, timezone

HR_DS_ID = "982a161a-945a-4c59-b6ce-7fd374e97967"


async def run_agent(question, user_role="admin", user_data_scope="all",
                    user_id="test-user", username="test",
                    employee_id=None, dept_id=None, dept_name="",
                    session_id=None, turn_history=None):
    """模拟完整的 Agent 问答流程"""
    print()
    print("=" * 72)
    print(f"  U0001f4ac 用户: {question}")
    print(f"  U0001f464 角色={user_role}, 范围={user_data_scope}", end="")
    if dept_name: print(f", 部门={dept_name}", end="")
    print()
    print("=" * 72)

    async with async_session() as db:
        # 获取数据源
        ds_result = await db.execute(select(DataSource).where(DataSource.id == HR_DS_ID))
        ds = ds_result.scalar_one_or_none()
        if not ds:
            print("  [❌] HR 数据源不存在")
            return None

        # 获取 Agent 并配置用户信息
        agent = agent_factory.get_or_create(ds)
        agent._user_role = user_role
        agent._user_data_scope = user_data_scope
        agent._user_id = user_id
        agent._user_employee_id = employee_id
        agent._user_dept_id = dept_id
        agent._user_dept_name = dept_name

        # RLS
        user_mock = User(
            id=user_id, username=username,
            role=user_role, data_scope=user_data_scope,
            employee_id=employee_id, dept_id=dept_id,
        )
        rls_engine = RowLevelSecurityEngine(user=user_mock, datasource=ds, db=db)
        rls_scope = await rls_engine.compute_data_scope()
        agent.set_rls_scope(rls_scope)

        turn_id = os.urandom(4).hex()
        session_id = session_id or turn_id

        # 构建上下文
        context = AgentContext(
            user_role=user_role, user_data_scope=user_data_scope,
            user_dept_name=dept_name, user_id=user_id,
            user_employee_id=employee_id, user_dept_id=dept_id,
            session_id=session_id, turn_number=(turn_history or []).__len__() + 1,
            is_followup=bool(session_id and turn_history),
            datasource_id=HR_DS_ID, business_tag="hr",
            db_session=db,
        )

        state = {
            "question": question, "original_question": question,
            "context": context, "turn_history": turn_history or [],
            "retry_count": 0, "intent_result": None, "sql_result": None,
            "analysis_result": None, "report_result": None,
            "messages": [],
        }

        # Step 1: 意图识别
        print("  [1/4] 意图识别...", end=" ", flush=True)
        intent_out = await intent_node(state)
        state["intent_result"] = intent_out.get("intent_result")
        intent_result = state["intent_result"]
        if intent_result and intent_result.status == "success":
            print(f"✅ {intent_result.intent_type.value} [{intent_result.analysis_depth}]")
        else:
            err = intent_result.error if intent_result else "None"
            print(f"❌ {err}")
            return state

        # Step 2: 路由决策
        route = route_by_intent(state)
        print(f"  [2/4] 路由: {route}")

        if route == "sql_node":
            # Step 3: SQL 查询
            print("  [3/4] SQL 查询...", end=" ", flush=True)
            user_info = {
                "role": user_role, "data_scope": user_data_scope,
                "employee_id": employee_id, "dept_id": dept_id,
            }
            result = await safe_query(question, agent, user_info)

            if result.get("status") == "success":
                df = result.get("data")
                sql = result.get("sql", "")
                rows = len(df) if df is not None else 0
                print(f"✅ {rows} 行")
                if sql: print(f"       SQL: {sql[:120]}...")

                # 封装 SQLResult
                from app.orchestrator.state import SQLResult
                state["sql_result"] = SQLResult(
                    status="success", sql=sql, df=df,
                    rows_affected=rows,
                )
            else:
                print(f"❌ {result.get('error', 'unknown')[:100]}")
                from app.orchestrator.state import SQLResult
                state["sql_result"] = SQLResult(
                    status="error", error=result.get("error", ""),
                )

            # 路由决策 2
            after_route = route_after_sql(state)
            print(f"       -> SQL 后路由: {after_route}")
        else:
            print("  [3/4] 跳过 SQL (直接报告)")

        # Step 4: 报告生成
        print("  [4/4] 报告生成...", end=" ", flush=True)
        report_out = await report_node(state)
        state["report_result"] = report_out.get("report_result")
        report_result = state["report_result"]

        if report_result and report_result.status == "success":
            print(f"✅ 已完成!")
            print()
            print("━" * 72)
            print("  U0001f4dd DataMind Agent 回答:")
            print("━" * 72)
            print(report_result.report_markdown)

            if report_result.followups:
                print()
                print("  U0001f4a1 你可以追问:")
                for f in report_result.followups:
                    print(f"    - {f}")
        else:
            err = report_result.error if report_result else "None"
            print(f"❌ {err}")

        print()
        return state


async def main():
    await init_db()
    print()
    print("━" * 72)
    print("  DataMind Agent 全链路 E2E 测试")
    print("  连接真实数据库 + DeepSeek API")
    print("  流程: Intent → SQL → Report")
    print("━" * 72)

    tests = [
        ("列出所有部门的名称", "admin", "all"),
        ("统计各部门的员工人数", "admin", "all"),
        ("绩效评分最高的前5名员工", "admin", "all"),
        ("员工的学历分布情况", "admin", "all"),
        ("你好", "admin", "all"),
    ]

    for question, role, scope in tests:
        try:
            await run_agent(question, role, scope)
        except Exception as e:
            import traceback
            print(f"  [❌] 异常: {e}")
            traceback.print_exc()

    print("━" * 72)
    print("  ✅ 测试全部完成!")
    print("━" * 72)


if __name__ == "__main__":
    asyncio.run(main())