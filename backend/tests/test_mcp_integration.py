"""
集成测试：MCP Server 查询引擎 — 覆盖 BETWEEN/IN/LIKE 过滤器、RLS 注入、权限矩阵
"""
import pytest
import os
os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

from app.mcp_servers.base_sql import _find_toplevel_keyword_v2, _find_where_end_v2
from app.core.query_rewriter import QueryInterceptor


class TestMCPQueryFilters:
    """测试 MCP 查询引擎的过滤器构建（BETWEEN/IN/LIKE）"""

    def test_find_toplevel_where(self):
        sql = "SELECT * FROM employees WHERE id = 1"
        assert _find_toplevel_keyword_v2(sql.upper(), "WHERE") == sql.upper().find("WHERE")

    def test_find_toplevel_ignores_subquery(self):
        sql = "SELECT * FROM (SELECT * FROM employees WHERE dept_id = 1) AS sub WHERE id = 1"
        pos = _find_toplevel_keyword_v2(sql.upper(), "WHERE")
        assert pos == sql.upper().rfind("WHERE")  # only toplevel WHERE

    def test_find_toplevel_between_not_confused(self):
        sql = 'SELECT "amount" FROM "budgets" WHERE "amount" BETWEEN 100 AND 200'
        pos = _find_toplevel_keyword_v2(sql.upper(), "WHERE")
        assert pos >= 0
        remainder = sql[pos:pos+15].upper()
        assert "BETWEEN" not in remainder  # WHERE position should be before BETWEEN

    def test_find_where_end_basic(self):
        sql = "SELECT * FROM employees WHERE id = 1"
        assert _find_where_end_v2(sql.upper(), sql.upper().find("WHERE") + 5) == len(sql)

    def test_find_where_end_with_group_by(self):
        sql = "SELECT dept_id, COUNT(*) FROM employees WHERE status = 'active' GROUP BY dept_id"
        where_end = _find_where_end_v2(sql.upper(), sql.upper().find("WHERE") + 5)
        assert sql[where_end:].strip().startswith("GROUP BY")


class TestQueryInterceptorV3:
    """测试 QueryInterceptor 的 RLS 注入（V3 实现）"""

    def test_rls_inject_with_between(self):
        """RLS 注入不应与 BETWEEN 冲突 — 使用 set_table_columns 提供精确列信息"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1, 2, 3)"},
        })
        interceptor.set_table_columns("budgets", ["id", "dept_id", "amount", "name"])
        sql = 'SELECT "amount" FROM "budgets" WHERE "amount" BETWEEN 100 AND 200'
        result = interceptor.rewrite_sql(sql, table_name="budgets")
        assert "dept_id IN" in result, f"RLS missing: {result}"
        assert "BETWEEN" in result, f"BETWEEN lost: {result}"


class TestMCPAuthMatrix:
    """测试 MCP Auth 权限矩阵"""

    def test_can_access_table_admin(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("admin", "all")
        assert auth.can_access_table("hr", "employees") == True
        assert auth.can_access_table("hr", "org_hierarchy") == True

    def test_can_access_table_employee(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("employee", "self_only")
        assert auth.can_access_table("hr", "employees") == True
        assert auth.can_access_table("hr", "org_hierarchy") == False

    def test_visible_columns_employee(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("employee", "self_only")
        cols = auth.visible_columns("hr", "employees")
        # employee has max_level={safe, sensitive}, so salary/sensitive is visible for filtering
        # but phone/email should be visible as 'sensitive' level too
        # the actual masking happens at _mask_sensitive_data time
        assert "name" in cols
        assert "dept_id" in cols

    def test_visible_columns_admin(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("admin", "all")
        cols = auth.visible_columns("hr", "employees")
        assert "salary" in cols
        assert "phone" in cols
        assert "email" in cols

    def test_mask_sensitive_data_employee(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("employee", "self_only")
        rows = [{"name": "张三", "salary": "100000", "phone": "13812348000", "email": "zhang@example.com"}]
        masked = auth.mask_sensitive_data("hr", rows)
        assert masked[0]["salary"] == "***"
        assert "****" in str(masked[0]["phone"])
        assert "***@" in str(masked[0]["email"])
        assert masked[0]["name"] == "张三"  # safe column stays

    def test_mask_sensitive_data_admin(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("admin", "all")
        rows = [{"name": "张三", "salary": "100000", "phone": "13812348000"}]
        masked = auth.mask_sensitive_data("hr", rows)
        assert masked[0]["salary"] == "100000"  # admin sees raw
        assert masked[0]["phone"] == "13812348000"

    def test_rls_filter_admin_returns_original(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("admin", "all", employee_id=1, dept_id=1)
        sql = 'SELECT * FROM "employees"'
        result = auth.apply_rls_filter("hr", "employees", sql)
        # admin data_scope=all should return original SQL
        assert result == sql

    def test_rls_filter_self_only(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("employee", "self_only", employee_id=42, dept_id=3)
        sql = 'SELECT * FROM "employees"'
        result = auth.apply_rls_filter("hr", "employees", sql)
        # self_only should add employee_id filter
        assert "42" in result or "employee_id" in result or '"id"' in result

    def test_rls_filter_dept_and_sub(self):
        from app.mcp_servers.base_sql import MCPAuth
        auth = MCPAuth("dept_manager", "dept_and_sub", employee_id=1, dept_id=1)
        sql = 'SELECT * FROM "employees"'
        result = auth.apply_rls_filter("hr", "employees", sql)
        assert "org_hierarchy" in result
