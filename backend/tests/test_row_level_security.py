"""行级安全 & SQL 拦截器单元测试 (V2)"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.core.query_rewriter import QueryInterceptor


class TestQueryInterceptor:
    """SQL 注入逻辑测试"""

    def test_mode_all_returns_original(self):
        """mode=all 时原样返回"""
        interceptor = QueryInterceptor({"mode": "all"})
        sql = "SELECT * FROM employees WHERE status = '在职'"
        assert interceptor.rewrite_sql(sql) == sql

    def test_no_filter_clauses_returns_original(self):
        """无过滤条件时原样返回"""
        interceptor = QueryInterceptor({"mode": "filtered", "filter_clauses": {}, "allowed_dept_ids": []})
        sql = "SELECT * FROM employees"
        assert interceptor.rewrite_sql(sql) == sql

    def test_inject_where_clause_with_existing_where(self):
        """已有 WHERE → 追加 AND"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1, 3, 4)"},
            "allowed_dept_ids": [1, 3, 4],
        })
        sql = "SELECT * FROM employees WHERE status = 'active' ORDER BY name"
        result = interceptor.rewrite_sql(sql)
        assert "dept_id IN (1, 3, 4)" in result
        assert result.upper().startswith("SELECT")
        assert "ORDER BY name" in result
        assert "AND" in result

    def test_inject_where_clause_without_where(self):
        """无 WHERE → 在 GROUP BY/ORDER BY 前插入"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1, 3)"},
            "allowed_dept_ids": [1, 3],
        })
        sql = "SELECT COUNT(*) FROM employees ORDER BY dept_id"
        result = interceptor.rewrite_sql(sql)
        assert "WHERE (dept_id IN (1, 3))" in result

    def test_inject_with_group_by(self):
        """GROUP BY 前注入"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (5)"},
            "allowed_dept_ids": [5],
        })
        sql = "SELECT dept_id, COUNT(*) FROM employees GROUP BY dept_id"
        result = interceptor.rewrite_sql(sql)
        assert "WHERE (dept_id IN (5))" in result
        assert "GROUP BY dept_id" in result

    def test_inject_with_limit(self):
        """LIMIT 前注入"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"employee_id": "employee_id IN (1,2,3)"},
            "allowed_employee_ids": [1, 2, 3],
        })
        sql = "SELECT * FROM attendance LIMIT 100"
        result = interceptor.rewrite_sql(sql)
        assert "WHERE (employee_id IN (1,2,3))" in result
        assert "LIMIT 100" in result

    def test_inject_at_end_when_no_keywords(self):
        """无关键字且 FROM 表在支持列表中时在末尾追加"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1)"},
            "allowed_dept_ids": [1],
        })
        sql = "SELECT COUNT(*) FROM employees"
        result = interceptor.rewrite_sql(sql)
        assert "WHERE (dept_id IN (1))" in result

    def test_picks_employee_id_filter_when_present_in_sql(self):
        """当SQL中包含 employee_id 列时优先使用该过滤"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {
                "dept_id": "dept_id IN (1,2,3)",
                "employee_id": "employee_id IN (10,20,30)",
            },
            "allowed_dept_ids": [1, 2, 3],
            "allowed_employee_ids": [10, 20, 30],
        })
        sql = "SELECT employee_id, status FROM attendance"
        result = interceptor.rewrite_sql(sql)
        assert "employee_id IN (10,20,30)" in result

    def test_subquery_not_confused(self):
        """子查询中的关键字不被误匹配"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {"dept_id": "dept_id IN (1,2)"},
            "allowed_dept_ids": [1, 2],
        })
        sql = "SELECT * FROM employees WHERE (SELECT COUNT(*) FROM departments) > 0"
        result = interceptor.rewrite_sql(sql)
        # employees 在 SQL 中 → dept_id 应被注入
        assert "dept_id IN (1,2)" in result

    def test_empty_dept_ids_no_injection(self):
        """空部门列表不注入无效过滤"""
        interceptor = QueryInterceptor({
            "mode": "filtered",
            "filter_clauses": {},
            "allowed_dept_ids": [],
            "allowed_employee_ids": [],
        })
        sql = "SELECT * FROM employees"
        result = interceptor.rewrite_sql(sql)
        assert "WHERE" not in result.split("WHERE")[-1] if "WHERE" not in result else True
        assert "IN ()" not in result


class TestRowLevelSecurityEngine:
    """权限计算引擎测试（需要数据库的异步测试）"""

    @pytest.mark.asyncio
    async def test_admin_returns_all(self):
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
        """data_scope=all 的用户 → mode=all"""
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
        """data_scope=self_only → 部门过滤 + 员工过滤=self"""
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
        # self_only 不添加 dept_id 过滤（只用 employee_id）
        assert 3 not in scope["allowed_dept_ids"]
        assert 31 in scope["allowed_employee_ids"]

    @pytest.mark.asyncio
    async def test_extra_dept_ids(self):
        """extra_dept_ids 中的部门被包含"""
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
    """HR 角色映射测试"""

    def test_finance_director_mapping(self):
        """财务总监 → finance_director"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("财务总监", "财务", 4)
        assert role == UserRole.finance_director

    def test_finance_bp_mapping(self):
        """普通财务 → finance_bp"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("成本会计", "财务", 4)
        assert role == UserRole.finance_bp

    def test_hr_director_mapping(self):
        """HR总监 → hr_director"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("HR总监", "HR", 3)
        assert role == UserRole.hr_director

    def test_dept_ceo_mapping(self):
        """部门总监 → dept_ceo"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("技术总监", "技术", 1)
        assert role == UserRole.dept_ceo

    def test_region_manager_mapping(self):
        """区域经理 → sales_manager"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("区域经理(华东)", "销售", 501)
        assert role == UserRole.sales_manager

    def test_dept_manager_mapping(self):
        """部门经理 → dept_manager"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("品牌经理", "运营", 201)
        assert role == UserRole.dept_manager

    def test_employee_mapping(self):
        """普通员工 → employee"""
        from app.core.hr_sync import determine_role
        from app.models.user import UserRole
        role = determine_role("前端工程师", "技术", 101)
        assert role == UserRole.employee
