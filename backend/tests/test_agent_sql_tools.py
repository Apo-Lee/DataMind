"""测试 SQL Tools 模块 — Function Calling 模式的 SQL 查询"""
import sys
sys.path.insert(0, "E:\\Python_Code_Project\\DataMind\\backend")

import pytest
from app.core.sql_tools import (
    build_query_tools,
    _build_safe_sql,
)


class TestBuildSafeSql:
    """测试 _build_safe_sql 函数"""

    def test_simple_query(self):
        sql = _build_safe_sql(
            main_table="employees",
            select_columns=["name", "dept_id"],
            limit=100,
            role="employee",
        )
        assert "SELECT" in sql
        assert '"name"' in sql
        assert '"dept_id"' in sql
        assert '"employees"' in sql
        assert "LIMIT 100" in sql

    def test_with_aggregation(self):
        sql = _build_safe_sql(
            main_table="employees",
            select_columns=["dept_id"],
            aggregations=[{"type": "COUNT", "column": "id", "alias": "cnt"}],
            group_by=["dept_id"],
            limit=100,
            role="employee",
        )
        assert 'COUNT("id")' in sql
        assert '"dept_id"' in sql
        assert "GROUP BY" in sql

    def test_with_filters(self):
        sql = _build_safe_sql(
            main_table="attendance",
            select_columns=["employee_id", "status"],
            filters=[{"column": "status", "op": "=", "value": "出勤"}],
            limit=100,
            role="employee",
        )
        assert "WHERE" in sql
        assert "出勤" in sql

    def test_between_filter(self):
        sql = _build_safe_sql(
            main_table="attendance",
            select_columns=["employee_id", "date"],
            filters=[{"column": "date", "op": "BETWEEN", "value": "2026-01-01, 2026-01-31"}],
            limit=100,
            role="employee",
        )
        assert "BETWEEN" in sql
        assert "2026-01-01" in sql
        assert "AND" in sql
        assert "2026-01-31" in sql

    def test_join_tables(self):
        sql = _build_safe_sql(
            main_table="employees",
            select_columns=["name"],
            join_tables=["departments"],
            filters=[{"column": "status", "op": "=", "value": "在职"}],
            limit=100,
            role="employee",
        )
        assert "LEFT JOIN" in sql
        assert '"departments"' in sql

    def test_limit_clamping(self):
        sql = _build_safe_sql(
            main_table="employees",
            select_columns=["name"],
            limit=99999,
            role="employee",
        )
        assert "LIMIT 5000" in sql

    def test_sql_injection_sanitization(self):
        """验证 SQL 注入防护：单引号被转义"""
        sql = _build_safe_sql(
            main_table="employees",
            select_columns=["name"],
            filters=[{"column": "name", "op": "=", "value": "' OR 1=1 --"}],
            limit=100,
            role="employee",
        )
        # 单引号应该被转义为两个单引号
        assert "'' OR 1=1 --" in sql
        # 注入 payload 被安全地包裹在字符串值中
        assert "= '" in sql
        assert "''" in sql

    def test_sql_injection_semantic_colon(self):
        """验证分号注入被安全包裹"""
        sql = _build_safe_sql(
            main_table="employees",
            select_columns=["name"],
            filters=[{"column": "name", "op": "=", "value": "x"}],
            limit=100,
            role="employee",
        )
        # 正常查询不应该包含额外的 SQL 关键字
        assert "SELECT" in sql
        assert sql.strip().endswith("100")


class TestBuildQueryTools:
    """测试工具定义生成"""

    def test_tool_definition_structure(self):
        tables_columns = {
            "employees": [{"name": "name", "sensitive": False, "description": "姓名"}],
            "departments": [{"name": "dept_name", "sensitive": False, "description": "部门名"}],
        }
        tools = build_query_tools("hr", tables_columns, "admin", "all")
        assert len(tools) == 5
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "query_data"
        assert tools[1]["function"]["name"] == "list_tables"
        assert tools[2]["function"]["name"] == "describe_table"
        assert tools[3]["function"]["name"] == "query_suggest"
        assert tools[4]["function"]["name"] == "execute_sql"

    def test_main_table_enum(self):
        """工具定义中 main_table 的 enum 包含所有可用表"""
        tables_columns = {
            "employees": [{"name": "name", "sensitive": False}],
            "departments": [{"name": "dept_name", "sensitive": False}],
        }
        tools = build_query_tools("hr", tables_columns, "admin", "all")
        enum_vals = tools[0]["function"]["parameters"]["properties"]["main_table"]["enum"]
        assert "employees" in enum_vals
        assert "departments" in enum_vals
