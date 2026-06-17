# -*- coding: utf-8 -*-
"""MCPAuth 权限回归测试 — 阶段0守护网

覆盖 MCP server 端真正在用的 MCPAuth（base_sql.py），保护后续 P0/P1 改动不引入权限回归：
  - apply_rls_filter   行级安全（RLS）按 data_scope 注入 WHERE
  - mask_sensitive_data  敏感字段脱敏（salary/phone/email）
  - can_access_table    表级访问控制（employee 禁访问 org_hierarchy）
  - filter_columns      列级可见性裁剪

注意：现有 test_row_level_security.py 测的是旧的 QueryInterceptor（query_rewriter），
与本测试覆盖的 MCPAuth 是两套实现。MCPAuth 才是 OrchestratorAgent → sql_node 链路真正依赖的。
"""
import pytest

from app.mcp_servers.base_sql import MCPAuth, Q

BT_HR = "hr"
BT_CRM = "crm"


# ---------------------------------------------------------------------------
# apply_rls_filter —— 行级安全（RLS）注入
# ---------------------------------------------------------------------------

class TestApplyRlsFilter:
    """验证不同 data_scope 下 SQL 被正确注入行级过滤条件。"""

    def test_admin_scope_all_returns_unchanged(self):
        """admin / data_scope=all → 不注入任何过滤，原 SQL 返回。"""
        auth = MCPAuth(user_role="admin", data_scope="all")
        sql = "SELECT * FROM employees"
        assert auth.apply_rls_filter(BT_HR, "employees", sql) == sql

    def test_employee_self_only_filters_by_employee_id(self):
        """普通员工 self_only → 注入 employee_id = X（employees 表的主键列）。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=42)
        sql = "SELECT * FROM employees"
        result = auth.apply_rls_filter(BT_HR, "employees", sql)
        # employees 表 fk 映射为 ("id", "employee_id")，self_only 用 cm[0]="id"
        assert f'"{Q}id{Q}" = 42' in result.replace('"', Q + "id" + Q) or "= 42" in result
        assert "WHERE" in result.upper()

    def test_dept_manager_team_filters_by_dept_id(self):
        """部门负责人 team/dept → 注入 dept_id = X（employees 表无 dept_fk，用 attendance 验证）。"""
        # employees 表 fk=("id","employee_id")，team 模式下用 cm[0]="id" —— 这其实有 bug 隐患，
        # 这里用 deals（fk=("dept_id","dept_id")）更贴近真实语义。
        auth = MCPAuth(user_role="dept_manager", data_scope="team", dept_id=7)
        sql = "SELECT * FROM deals"
        result = auth.apply_rls_filter(BT_CRM, "deals", sql)
        assert "= 7" in result
        assert "WHERE" in result.upper()

    def test_hr_director_dept_and_sub_uses_org_hierarchy(self):
        """hr_director / dept_and_sub → 注入 IN (SELECT descendant_id FROM org_hierarchy ...)。"""
        auth = MCPAuth(user_role="hr_director", data_scope="dept_and_sub", dept_id=3)
        sql = "SELECT * FROM departments"
        result = auth.apply_rls_filter(BT_HR, "departments", sql)
        assert "descendant_id" in result
        assert "org_hierarchy" in result
        assert "ancestor_id" in result and "= 3" in result

    def test_rls_preserves_existing_where(self):
        """已有 WHERE 时用 AND 追加，而非覆盖。"""
        auth = MCPAuth(user_role="dept_manager", data_scope="team", dept_id=5)
        sql = "SELECT * FROM deals WHERE status = 'open'"
        result = auth.apply_rls_filter(BT_CRM, "deals", sql)
        # 原 status 条件必须保留
        assert "status" in result
        assert "= 5" in result
        assert "AND" in result.upper()

    def test_rls_appends_before_order_by_limit(self):
        """无 WHERE 但有 ORDER BY / LIMIT 时，WHERE 应插在它们前面（阶段1已修复）。"""
        auth = MCPAuth(user_role="dept_manager", data_scope="team", dept_id=5)
        sql = "SELECT * FROM deals ORDER BY amount DESC LIMIT 10"
        result = auth.apply_rls_filter(BT_CRM, "deals", sql)
        upper = result.upper()
        where_idx = upper.find("WHERE")
        order_idx = upper.find("ORDER BY")
        limit_idx = upper.find("LIMIT")
        assert where_idx != -1 and order_idx != -1 and limit_idx != -1
        assert where_idx < order_idx < limit_idx

    def test_rls_no_employee_id_self_only_skips_filter(self):
        """self_only 但 employee_id=None → 安全跳过（不注入，避免空过滤导致全表）。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=None)
        sql = "SELECT * FROM employees"
        # employee_id 缺失时不应注入条件（返回原 SQL）
        assert auth.apply_rls_filter(BT_HR, "employees", sql) == sql

    def test_unknown_table_no_fk_returns_unchanged(self):
        """表不在 fk 映射里 → 无法注入，原样返回（不崩）。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        sql = "SELECT * FROM some_unknown_table"
        assert auth.apply_rls_filter(BT_HR, "some_unknown_table", sql) == sql


# ---------------------------------------------------------------------------
# mask_sensitive_data —— 敏感字段脱敏
# ---------------------------------------------------------------------------

class TestMaskSensitiveData:
    """验证敏感字段按角色可见性脱敏。"""

    BASE_ROWS = [{
        "name": "张三", "salary": 25000, "phone": "13800138000",
        "email": "zhangsan@example.com", "dept_id": 3,
    }]

    def test_admin_no_masking(self):
        """admin max_level 含 highly_sensitive → 不脱敏，原样返回。"""
        auth = MCPAuth(user_role="admin", data_scope="all")
        out = auth.mask_sensitive_data(BT_HR, self.BASE_ROWS)
        assert out[0]["salary"] == 25000
        assert out[0]["phone"] == "13800138000"
        assert out[0]["email"] == "zhangsan@example.com"

    def test_employee_masks_sensitive_fields(self):
        """employee max_level = {safe, sensitive}，sensitive 字段应被脱敏（阶段1已修复）。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        out = auth.mask_sensitive_data(BT_HR, self.BASE_ROWS)
        # salary（非 phone/email 特殊处理）→ ***
        assert out[0]["salary"] == "***"
        # phone 11 位 → 前3+****+后4
        assert out[0]["phone"] == "138****8000"
        # email → 前2+***@domain
        assert out[0]["email"] == "zh***@example.com"
        # safe 字段不动
        assert out[0]["name"] == "张三"
        assert out[0]["dept_id"] == 3

    def test_viewer_masks_sensitive_fields(self):
        """viewer max_level = {safe}，同样需脱敏 sensitive。"""
        auth = MCPAuth(user_role="viewer", data_scope="dept")
        out = auth.mask_sensitive_data(BT_HR, self.BASE_ROWS)
        assert out[0]["salary"] == "***"
        assert out[0]["phone"] == "138****8000"

    def test_does_not_mutate_input(self):
        """脱敏不应修改原始 rows（返回的是 dict 副本）。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        original_salary = self.BASE_ROWS[0]["salary"]
        auth.mask_sensitive_data(BT_HR, self.BASE_ROWS)
        assert self.BASE_ROWS[0]["salary"] == original_salary

    def test_empty_rows_returns_empty(self):
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        assert auth.mask_sensitive_data(BT_HR, []) == []


# ---------------------------------------------------------------------------
# can_access_table —— 表级访问控制
# ---------------------------------------------------------------------------

class TestCanAccessTable:
    """验证表级准入：employee 禁访问 org_hierarchy，其他角色放行。"""

    def test_admin_can_access_any_table(self):
        auth = MCPAuth(user_role="admin", data_scope="all")
        assert auth.can_access_table(BT_HR, "org_hierarchy") is True
        assert auth.can_access_table(BT_HR, "employees") is True

    def test_employee_cannot_access_org_hierarchy(self):
        """关键安全断言：employee 不能读组织架构表（含全公司部门关系）。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        assert auth.can_access_table(BT_HR, "org_hierarchy") is False

    def test_employee_can_access_normal_tables(self):
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        assert auth.can_access_table(BT_HR, "employees") is True
        assert auth.can_access_table(BT_HR, "attendance") is True

    def test_other_roles_can_access_org_hierarchy(self):
        for role in ("hr_director", "dept_manager", "dept_ceo"):
            auth = MCPAuth(user_role=role, data_scope="team", dept_id=1)
            assert auth.can_access_table(BT_HR, "org_hierarchy") is True, role


# ---------------------------------------------------------------------------
# filter_columns —— 列级可见性裁剪
# ---------------------------------------------------------------------------

class TestFilterColumns:
    """验证按角色裁剪可见列。"""

    def test_employee_gets_all_declared_columns(self):
        """employee max_level 含 sensitive → 返回所有已声明列（含 sensitive 字段名）。

        filter_columns 是裁剪"列名"，不是脱敏"值"。employee 能看到 salary 列存在。
        """
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        cols = ["name", "salary", "phone", "email", "dept_id"]
        out = auth.filter_columns(BT_HR, "employees", cols)
        # employee max_level={safe,sensitive}，全部列都可见
        assert set(out) == {"name", "salary", "phone", "email", "dept_id"}

    def test_admin_returns_all_columns(self):
        auth = MCPAuth(user_role="admin", data_scope="all")
        cols = ["name", "salary", "phone"]
        out = auth.filter_columns(BT_HR, "employees", cols)
        assert set(out) == {"name", "salary", "phone"}

    def test_unknown_table_returns_input_unchanged(self):
        """表不在 sensitivity 映射 → visible_columns 为空 → 原样返回输入。"""
        auth = MCPAuth(user_role="employee", data_scope="self_only", employee_id=1)
        cols = ["a", "b", "c"]
        assert auth.filter_columns(BT_HR, "nonexistent_table", cols) == cols
