"""SQL 查询拦截器 (V3) — 在执行前注入行级权限过滤条件

V3 改进：
- SQLBuilder 不再内联 RLS，RLS 统一由此拦截器注入
- 精确列存在性检查 — 只注入目标表实际存在的列（通过 set_table_columns）
- 修复重复注入问题（只注入一次）
- 对于 departments 等无 dept_id/employee_id 的表跳过 RLS
"""


class QueryInterceptor:
    """在 SQL 执行前注入行级安全过滤"""

    def __init__(self, rls_scope: dict):
        self.scope = rls_scope
        self._column_cache: dict[str, set[str]] = {}

    def rewrite_sql(self, original_sql: str, table_name: str | None = None) -> str:
        """重写 SQL：在 WHERE 子句中注入 RLS 过滤条件"""
        if self.scope.get("mode") == "all":
            return original_sql

        filter_clauses = self.scope.get("filter_clauses", {})
        if not filter_clauses:
            return original_sql

        matching_clause = self._pick_exact_filter(table_name, filter_clauses, original_sql)
        if not matching_clause:
            return original_sql

        return self._inject_where_clause(original_sql, matching_clause)

    def set_table_columns(self, table_name: str, columns: list[str]):
        """设置指定表的列名列表，用于精确列存在性检查"""
        self._column_cache[table_name.lower()] = {c.lower() for c in columns}

    def _pick_exact_filter(self, table_name: str | None, clauses: dict, sql: str) -> str | None:
        """精确选择过滤子句：只选目标表实际存在的列"""
        if not table_name:
            return self._pick_filter_fallback(clauses, sql)

        tbl_lower = table_name.lower()
        cached_cols = self._column_cache.get(tbl_lower, None)

        if cached_cols is not None:
            for col in ("employee_id", "dept_id", "owner_id", "owner_dept_id", "manager_id", "approver_id", "id"):
                clause = clauses.get(col)
                if clause and col.lower() in cached_cols:
                    return clause
            return None

        sql_lower = sql.lower()
        sql_upper = sql.upper()
        no_dept_tables = {"departments", "org_hierarchy", "kpi_preferences", "conversations"}
        if tbl_lower in no_dept_tables:
            if "employee_id" in clauses and "employee_id" in sql_upper:
                return clauses["employee_id"]
            return None

        if tbl_lower == "attendance":
            if "employee_id" in clauses and "employee_id" in sql_lower:
                return clauses["employee_id"]
            return None

        if tbl_lower == "customers":
            if "owner_id" in clauses and "owner_id" in sql_lower:
                return clauses["owner_id"]
            if "owner_dept_id" in clauses and "owner_dept_id" in sql_lower:
                return clauses["owner_dept_id"]
            return None

        return self._pick_filter_fallback(clauses, sql)

    @staticmethod
    def _pick_filter_fallback(clauses: dict, sql: str) -> str | None:
        sql_upper = sql.upper()
        for col in ("employee_id", "dept_id", "owner_id", "owner_dept_id", "manager_id"):
            clause = clauses.get(col)
            if clause and col.upper() in sql_upper:
                return clause
        clause = clauses.get("id")
        if clause:
            return clause
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
