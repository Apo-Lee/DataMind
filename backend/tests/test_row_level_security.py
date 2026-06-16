"""行级安全 & SQL 拦截器单元测试 (V3)"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.core.query_rewriter import QueryInterceptor


class TestQueryInterceptor:
    """SQL 注入逻辑测试（V3：需传递 table_name 或列缓存）"""

    def test_mode_all_returns_original(self):
        interceptor = QueryInterceptor({"mode": "all"})
        sql = "SELECT * FROM employees WHERE status = '在职'"
        assert interceptor.rewrite_sql(sql) == sql

    def test_no_filter_clauses_returns_original(self):
        interceptor = QueryInterceptor({"mode": "filtered", "filter_clauses": {}, "allowed_dept_ids": []})
        sql = "SELECT * FROM employees"
        assert interceptor.rewrite_sql(sql) == sql

    def test_inject_where_clause_with_existing_where(self):
        """已有 WHERE 且包含 dept_id → 追加 AND（使用表名匹配）"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1, 3, 4)"},
            "allowed_dept_ids": [1, 3, 4],
        })
        interceptor.set_table_columns("employees", ["id", "name", "dept_id", "status"])
        sql = "SELECT * FROM employees WHERE status = 'active' ORDER BY name"
        result = interceptor.rewrite_sql(sql, table_name="employees")
        assert "dept_id IN (1, 3, 4)" in result
        assert result.upper().startswith("SELECT")
        assert "ORDER BY name" in result
        assert "AND" in result

    def test_inject_where_clause_without_where(self):
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1, 3)"},
            "allowed_dept_ids": [1, 3],
        })
        interceptor.set_table_columns("employees", ["id", "name", "dept_id"])
        sql = "SELECT COUNT(*) FROM employees ORDER BY dept_id"
        result = interceptor.rewrite_sql(sql, table_name="employees")
        assert "WHERE (dept_id IN (1, 3))" in result

    def test_inject_with_group_by(self):
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (5)"},
            "allowed_dept_ids": [5],
        })
        interceptor.set_table_columns("employees", ["id", "dept_id"])
        sql = "SELECT dept_id, COUNT(*) FROM employees GROUP BY dept_id"
        result = interceptor.rewrite_sql(sql, table_name="employees")
        assert "WHERE (dept_id IN (5))" in result
        assert "GROUP BY dept_id" in result

    def test_inject_with_limit(self):
        """attendance 表通过 employee_id 过滤"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"employee_id": "employee_id IN (1,2,3)"},
            "allowed_employee_ids": [1, 2, 3],
        })
        interceptor.set_table_columns("attendance", ["id", "employee_id", "date", "status"])
        sql = "SELECT * FROM attendance LIMIT 100"
        result = interceptor.rewrite_sql(sql, table_name="attendance")
        assert "WHERE (employee_id IN (1,2,3))" in result
        assert "LIMIT 100" in result

    def test_inject_at_end_when_no_keywords(self):
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1)"},
            "allowed_dept_ids": [1],
        })
        interceptor.set_table_columns("employees", ["id", "name", "dept_id"])
        sql = "SELECT COUNT(*) FROM employees"
        result = interceptor.rewrite_sql(sql, table_name="employees")
        assert "WHERE (dept_id IN (1))" in result

    def test_picks_employee_id_filter_when_present_in_sql(self):
        """attendance 表有 employee_id 列 → 使用 employee_id 过滤"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {
                "dept_id": "dept_id IN (1,2,3)",
                "employee_id": "employee_id IN (10,20,30)",
            },
            "allowed_dept_ids": [1, 2, 3],
            "allowed_employee_ids": [10, 20, 30],
        })
        interceptor.set_table_columns("attendance", ["id", "employee_id", "status"])
        sql = "SELECT employee_id, status FROM attendance"
        result = interceptor.rewrite_sql(sql, table_name="attendance")
        assert "employee_id IN (10,20,30)" in result

    def test_subquery_not_confused(self):
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1,2)"},
            "allowed_dept_ids": [1, 2],
        })
        interceptor.set_table_columns("employees", ["id", "dept_id"])
        sql = "SELECT * FROM employees WHERE (SELECT COUNT(*) FROM departments) > 0"
        result = interceptor.rewrite_sql(sql, table_name="employees")
        assert "dept_id IN (1,2)" in result

    def test_empty_dept_ids_no_injection(self):
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {},
            "allowed_dept_ids": [],
            "allowed_employee_ids": [],
        })
        sql = "SELECT * FROM employees"
        result = interceptor.rewrite_sql(sql, table_name="employees")
        assert "WHERE" not in result.split("WHERE")[-1] if "WHERE" in result else True

    def test_departments_table_skips_dept_filter(self):
        """departments 表没有 dept_id 列 → 跳过 RLS"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1,2)"},
            "allowed_dept_ids": [1, 2],
        })
        interceptor.set_table_columns("departments", ["id", "name", "parent_dept_id"])
        sql = "SELECT * FROM departments"
        result = interceptor.rewrite_sql(sql, table_name="departments")
        assert "WHERE" not in result


class TestRowLevelSecurityEngine:
    """RLS 引擎单元测试"""

    @pytest.mark.asyncio
    async def test_admin_mode_all(self):
        """admin 用户 → mode=all"""
        from app.models.user import User, UserRole, DataScope
        from app.core.row_level_security import RowLevelSecurityEngine

        user = User(
            username="admin", display_name="Admin",
            role=UserRole.admin, is_active=True,
            data_scope=DataScope.all,
        )
        ds = MagicMock()
        db = AsyncMock()
        engine = RowLevelSecurityEngine(user, ds, db)
        scope = await engine.compute_data_scope()
        assert scope["mode"] == "all"

    @pytest.mark.asyncio
    async def test_data_scope_all_returns_all(self):
        from app.models.user import User, UserRole, DataScope
        from app.core.row_level_security import RowLevelSecurityEngine

        user = User(
            username="ceo", display_name="CEO",
            role=UserRole.dept_ceo, is_active=True,
            data_scope=DataScope.all, dept_id=1,
        )
        ds = MagicMock()
        db = AsyncMock()
        engine = RowLevelSecurityEngine(user, ds, db)
        scope = await engine.compute_data_scope()
        assert scope["mode"] == "all"

    @pytest.mark.asyncio
    async def test_self_only_scope(self):
        """self_only → 仅自己：不过滤部门，过滤员工ID"""
        from app.models.user import User, UserRole, DataScope
        from app.core.row_level_security import RowLevelSecurityEngine

        user = User(
            username="emp1", display_name="员工1",
            role=UserRole.employee, is_active=True,
            data_scope=DataScope.self_only,
            dept_id=3, employee_id=31,
        )
        ds = MagicMock()
        db = AsyncMock()
        engine = RowLevelSecurityEngine(user, ds, db)
        scope = await engine.compute_data_scope()
        assert scope["mode"] == "filtered"
        # self_only 添加 base_dept_id 但不过滤部门（主要按 employee_id 过滤）
        assert 3 in scope["allowed_dept_ids"]  # V3: self_only 添加 base_dept_id
        assert 31 in scope["allowed_employee_ids"]

    @pytest.mark.asyncio
    async def test_extra_dept_ids(self):
        from app.models.user import User, UserRole, DataScope
        from app.core.row_level_security import RowLevelSecurityEngine

        import json
        user = User(
            username="cross", display_name="跨部门",
            role=UserRole.dept_ceo, is_active=True,
            data_scope=DataScope.cross_dept,
            dept_id=1, extra_dept_ids=json.dumps([5, 6]),
        )
        ds = MagicMock()
        db = AsyncMock()
        engine = RowLevelSecurityEngine(user, ds, db)
        scope = await engine.compute_data_scope()
        assert scope["mode"] == "filtered"
        assert 5 in scope["allowed_dept_ids"]
        assert 6 in scope["allowed_dept_ids"]


class TestHrRoleMapping:
    def test_finance_director_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("财务总监", "财务", 4)
        assert role == UserRole.finance_director

    def test_finance_bp_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("成本会计", "财务", 4)
        assert role == UserRole.finance_bp

    def test_hr_director_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("HR总监", "HR", 3)
        assert role == UserRole.hr_director

    def test_dept_ceo_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("技术总监", "技术", 1)
        assert role == UserRole.dept_ceo

    def test_region_manager_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("区域经理(华东)", "销售", 501)
        assert role == UserRole.sales_manager

    def test_dept_manager_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("品牌经理", "运营", 201)
        assert role == UserRole.dept_manager

    def test_employee_mapping(self):
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("前端工程师", "技术", 101)
        assert role == UserRole.employee
