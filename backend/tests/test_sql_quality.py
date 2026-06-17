"""DataMind LangGraph Agent - SQL 生成质量测试"""
import os, json
os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

import pandas as pd
import pytest

from app.agents.base import ColumnInfo, TableSchema
# safe_query 已统一到 OrchestratorAgent（阶段2），旧路径测试标记为 xfail 并保留条目待后续重写


class MockHRAgent:
    """模拟 HR 数据源 Agent"""
    business_tag = "hr"
    datasource_id = "ds-hr-mock"

    def __init__(self):
        self._user_role = "dept_manager"
        self._user_data_scope = "dept"
        self._user_dept_name = "技术部"
        self._user_id = "user-001"
        self._user_employee_id = 1
        self._user_dept_id = 1
        self._rls_scope = None

    def set_rls_scope(self, scope):
        self._rls_scope = scope

    def list_tables(self):
        return ["employees", "departments", "attendance", "org_hierarchy"]

    def describe_table(self, table_name):
        schemas = {
            "employees": [
                ("id", "INTEGER", False, True),
                ("name", "TEXT", True, False),
                ("dept_id", "INTEGER", False, False),
                ("position", "TEXT", False, False),
                ("level", "TEXT", False, False),
                ("status", "TEXT", False, False),
                ("join_date", "TEXT", False, False),
                ("salary", "REAL", False, False),
                ("performance_score", "REAL", False, False),
                ("phone", "TEXT", False, False),
                ("email", "TEXT", False, False),
                ("manager_id", "INTEGER", False, False),
                ("position_category", "TEXT", False, False),
                ("gender", "TEXT", False, False),
                ("education", "TEXT", False, False),
            ],
            "departments": [
                ("id", "INTEGER", False, True),
                ("name", "TEXT", True, False),
                ("parent_dept_id", "INTEGER", False, False),
                ("manager_name", "TEXT", False, False),
                ("budget", "REAL", False, False),
                ("location", "TEXT", False, False),
            ],
            "attendance": [
                ("id", "INTEGER", False, True),
                ("employee_id", "INTEGER", False, False),
                ("date", "TEXT", False, False),
                ("check_in", "TEXT", False, False),
                ("check_out", "TEXT", False, False),
                ("status", "TEXT", False, False),
            ],
            "org_hierarchy": [
                ("ancestor_id", "INTEGER", False, True),
                ("descendant_id", "INTEGER", False, True),
                ("depth", "INTEGER", False, False),
            ],
        }
        cols = schemas.get(table_name, [])
        pk_cols = ["ancestor_id", "descendant_id"] if table_name == "org_hierarchy" else [c[0] for c in cols if c[3]]
        columns = [
            ColumnInfo(name=c[0], dtype=c[1], nullable=c[2], is_primary_key=c[0] in pk_cols)
            for c in cols
        ]
        table = TableSchema(name=table_name, columns=columns)
        table.row_count = {"employees": 50, "departments": 20, "attendance": 500, "org_hierarchy": 200}.get(table_name, 100)
        return table

    def execute_sql(self, sql, params=None):
        return pd.DataFrame({"result": ["mock data"]})

    async def execute_sql_async(self, sql, params=None):
        return self.execute_sql(sql, params)


@pytest.mark.skip(reason="safe_query 已移除（阶段2.3），需在 OrchestratorAgent 路径下重写")
@pytest.mark.asyncio
async def test_sql_generation_simple_count():
    """简单计数查询（旧路径，待重写）"""
    from app.core.query_engine import safe_query  # noqa: F811
    agent = MockHRAgent()
    result = await safe_query("技术部有多少员工", agent, {
        "role": "dept_manager", "data_scope": "dept",
        "employee_id": 1, "dept_id": 1,
    })
    assert not result.get("rejected"), f"查询被拒绝: {result.get('error')}"
    sql = result.get("sql", "")
    assert "SELECT" in sql


@pytest.mark.skip(reason="safe_query 已移除（阶段2.3），需在 OrchestratorAgent 路径下重写")
@pytest.mark.asyncio
async def test_sql_generation_aggregation():
    """聚合统计查询（旧路径，待重写）"""
    from app.core.query_engine import safe_query  # noqa: F811
    agent = MockHRAgent()
    result = await safe_query("各部门的平均绩效评分", agent, {
        "role": "dept_manager", "data_scope": "dept",
        "employee_id": 1, "dept_id": 1,
    })
    assert not result.get("rejected"), f"查询被拒绝: {result.get('error')}"
    sql = result.get("sql", "")
    assert "SELECT" in sql
    assert "AVG" in sql or "avg" in sql
    assert "GROUP BY" in sql


@pytest.mark.skip(reason="safe_query 已移除（阶段2.3），需在 OrchestratorAgent 路径下重写")
@pytest.mark.asyncio
async def test_sql_generation_filter():
    """带过滤的查询（旧路径，待重写）"""
    from app.core.query_engine import safe_query  # noqa: F811
    agent = MockHRAgent()
    result = await safe_query("本月请假人数", agent, {
        "role": "dept_manager", "data_scope": "dept",
        "employee_id": 1, "dept_id": 1,
    })
    assert not result.get("rejected"), f"查询被拒绝: {result.get('error')}"
    sql = result.get("sql", "")
    assert "SELECT" in sql
    assert "请假" in sql


@pytest.mark.skip(reason="safe_query 已移除（阶段2.3），需在 OrchestratorAgent 路径下重写")
@pytest.mark.asyncio
async def test_sql_generation_safety():
    """安全检查（旧路径，待重写）"""
    from app.core.query_engine import safe_query  # noqa: F811
    agent = MockHRAgent()
    result = await safe_query("列出所有部门名称", agent, {
        "role": "dept_manager", "data_scope": "dept",
        "employee_id": 1, "dept_id": 1,
    })
    assert not result.get("rejected"), f"查询被拒绝: {result.get('error')}"
    sql = result.get("sql", "")
    sql_upper = sql.upper()
    assert sql_upper.strip().startswith("SELECT"), "不是 SELECT 语句"
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    for kw in dangerous:
        assert kw not in sql_upper, f"包含危险操作: {kw}"
    assert "LIMIT" in sql_upper, "没有 LIMIT"


@pytest.mark.skip(reason="safe_query 已移除（阶段2.3），需在 OrchestratorAgent 路径下重写权限测试")
async def test_sql_generation_permission_employee_salary():
    """employee 角色应被拒绝查询薪资（旧路径，待重写）"""
    from app.core.query_engine import safe_query  # noqa: F811
    agent = MockHRAgent()
    agent._user_role = "employee"
    result = await safe_query("所有人的薪资是多少", agent, {
        "role": "employee", "data_scope": "self_only",
        "employee_id": 1, "dept_id": 1,
    })
    assert result.get("rejected"), "employee 角色查询薪资未被拒绝"


@pytest.mark.skip(reason="safe_query 已移除（阶段2.3），需在 OrchestratorAgent 路径下重写")
async def test_sql_generation_with_join():
    """JOIN 查询（旧路径，待重写）"""
    from app.core.query_engine import safe_query  # noqa: F811
    agent = MockHRAgent()
    result = await safe_query("各部门员工人数", agent, {
        "role": "dept_manager", "data_scope": "dept",
        "employee_id": 1, "dept_id": 1,
    })
    assert not result.get("rejected"), f"查询被拒绝: {result.get('error')}"
    sql = result.get("sql", "")
    assert "SELECT" in sql
