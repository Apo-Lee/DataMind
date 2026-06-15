"""SQL 查询拦截器 (V2) — 在执行前注入行级权限过滤条件"""


class QueryInterceptor:
    """在 SQL 执行前注入行级安全过滤"""

    # 已知含 dept_id 列的表（小写）
    DEPT_TABLES = frozenset([
        "employees", "deals", "expenses", "projects", "sales_targets",
        "budgets", "travel_expenses", "purchase_orders",
        "cost_centers", "inventory", "project_dept",
    ])
    # 已知含 employee_id 列的表（小写，不包括 employees——employees 用 id 列）
    EMP_TABLES = frozenset([
        "attendance", "expenses", "follow_ups", "resources",
        "sales_targets", "travel_expenses", "purchase_orders",
    ])
    # 已知含 id 列（员工号主键） 的表（小写）
    ID_TABLES = frozenset(["employees"])
    # 列替代映射：表中无 dept_id/employee_id 但有替代列
    ALT_COLUMNS = {
        "customers": {"employee_id": "owner_id", "dept_id": "owner_dept_id", "id": "owner_id"},
        "deals": {"employee_id": "owner_id"},
        "projects": {"employee_id": "manager_id"},
    }

    def __init__(self, rls_scope: dict):
        self.scope = rls_scope

    def rewrite_sql(self, original_sql: str, table_name: str | None = None) -> str:
        if self.scope.get("mode") == "all":
            return original_sql
        filter_clauses = self.scope.get("filter_clauses", {})
        if not filter_clauses:
            return original_sql
        filter_clause = self._pick_filter_clause(filter_clauses, table_name, original_sql)
        if not filter_clause:
            return original_sql
        return self._inject_where_clause(original_sql, filter_clause)

    def _pick_filter_clause(self, clauses: dict, table_name: str | None, sql: str) -> str | None:
        sql_upper = sql.upper()
        sql_lower = sql.lower()

        # Step 1: 列名精确出现在 SQL 中（排除 id——太泛化）
        for col in ("dept_id", "employee_id", "owner_id", "approver_id",
                     "manager_id", "owner_dept_id", "requester_id", "requester_dept_id"):
            if col in clauses and col.upper() in sql_upper:
                return clauses[col]

        # Step 2: 通过表名匹配找到最佳列
        # 2a: 先找 ALT_COLUMNS 映射（处理无标准列的表）
        for tbl, alt_map in self.ALT_COLUMNS.items():
            if tbl in sql_lower:
                for orig_col, alt_col in alt_map.items():
                    if alt_col in clauses:
                        return clauses[alt_col]

        # 2b: employee_id 表匹配（优先于 dept_id，更精确）
        if "employee_id" in clauses:
            for tbl in self.EMP_TABLES:
                if tbl in sql_lower:
                    return clauses["employee_id"]

        # 2c: dept_id 表匹配
        if "dept_id" in clauses:
            for tbl in self.DEPT_TABLES:
                if tbl in sql_lower:
                    return clauses["dept_id"]

        # 2d: id 表匹配（employees 主键）
        if "id" in clauses:
            for tbl in self.ID_TABLES:
                if tbl in sql_lower:
                    return clauses["id"]

        return None

    def _inject_where_clause(self, sql: str, filter_clause: str) -> str:
        sql = sql.rstrip(";").rstrip()
        sql_upper = sql.upper()
        where_pos = self._find_toplevel_keyword(sql_upper, "WHERE")
        if where_pos >= 0:
            end_pos = self._find_where_end(sql_upper, where_pos + 5)
            return f"{sql[:end_pos]} AND ({filter_clause}){sql[end_pos:]}"
        for keyword in ("GROUP BY", "ORDER BY", "LIMIT", "HAVING"):
            pos = self._find_toplevel_keyword(sql_upper, keyword)
            if pos >= 0:
                return f"{sql[:pos]} WHERE ({filter_clause}) {sql[pos:]}"
        return f"{sql} WHERE ({filter_clause})"

    @staticmethod
    def _find_toplevel_keyword(sql_upper: str, keyword: str) -> int:
        depth = 0
        kw_len = len(keyword)
        for i in range(len(sql_upper) - kw_len + 1):
            ch = sql_upper[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif depth == 0 and sql_upper[i:i + kw_len] == keyword:
                prev_ok = i == 0 or sql_upper[i - 1] in (' ', '\n', '\t')
                next_ok = i + kw_len >= len(sql_upper) or sql_upper[i + kw_len] in (' ', '\n', '\t')
                if prev_ok and next_ok:
                    return i
        return -1

    @staticmethod
    def _find_where_end(sql_upper: str, start: int) -> int:
        end = len(sql_upper)
        for kw in ("GROUP BY", "ORDER BY", "LIMIT", "HAVING", "UNION"):
            pos = QueryInterceptor._find_toplevel_keyword(sql_upper, kw)
            if start < pos < end:
                end = pos
        return end
