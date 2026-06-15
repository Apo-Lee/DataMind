"""SQL 查询拦截器 (V3) — 在执行前注入行级权限过滤条件

V3 变化：
- SQLBuilder 不再内联 RLS，RLS 统一由此拦截器注入
- 加入列存在性检查 — 只注入目标表实际存在的列
- 修复重复注入问题
"""


class QueryInterceptor:
    """在 SQL 执行前注入行级安全过滤"""

    def __init__(self, rls_scope: dict):
        self.scope = rls_scope

    def rewrite_sql(self, original_sql: str, table_name: str | None = None) -> str:
        """重写 SQL：在 WHERE 子句中注入 RLS 过滤条件

        Args:
            original_sql: 原始 SQL（不含 RLS）
            table_name: 主表名，用于列存在性检查

        V3: 只注入一次，不做列名猜测（SQLBuilder 已无 RLS）
        """
        if self.scope.get("mode") == "all":
            return original_sql

        filter_clauses = self.scope.get("filter_clauses", {})
        if not filter_clauses:
            return original_sql

        filter_clause = self._pick_filter_clause(filter_clauses, table_name, original_sql)

        if not filter_clause:
            return original_sql

        return self._inject_where_clause(original_sql, filter_clause)

    def set_table_columns(self, table_name: str, columns: list[str]):
        """设置指定表的列名列表，用于精确列存在性检查"""
        self._column_cache = getattr(self, "_column_cache", {})
        self._column_cache[table_name.lower()] = {c.lower() for c in columns}

    def _has_column(self, col_name: str, sql: str) -> bool:
        """检查列名是否在 SQL 的 FROM 子句的主表中存在"""
        cache = getattr(self, "_column_cache", {})
        if not cache:
            # 无缓存时：通过 SQL 文本判断列是否已被引用
            sql_lower = sql.lower()
            return col_name.lower() in sql_lower
        # 有缓存时：检查列名在已缓存的任意表中是否存在
        col_lower = col_name.lower()
        for tbl, cols in cache.items():
            if col_lower in cols:
                # 确认该表确实在 SQL 中出现
                if tbl in sql.lower():
                    return True
        return False

    def _pick_filter_clause(self, clauses: dict, table_name: str | None, sql: str) -> str | None:
        """选择最适合的过滤子句

        V3: 只选一个最匹配的，不重复注入
        """
        sql_lower = sql.lower()
        sql_upper = sql.upper()

        # V3: 优先选择列名精确出现在 SQL 中的
        # 注意：对于 attendance 等无 dept_id 的表，dept_id 会跳过
        for col in ("employee_id", "dept_id", "owner_id", "owner_dept_id", "manager_id", "approver_id"):
            if col in clauses and col.upper() in sql_upper:
                # attendance 表没有 dept_id — 检查并跳过
                if col == "dept_id" and "attendance" in sql_lower:
                    continue
                return clauses[col]

        # 针对已知无 dept_id 但可能有其他过滤列的表
        # departments: 只有 id, name, parent_dept_id, manager_name, budget, location
        # V3: 对于 departments 这类表，跳过 RLS 部门过滤
        no_dept_tables = {"departments", "org_hierarchy", "kpi_preferences", "conversations"}
        for t in no_dept_tables:
            if t in sql_lower:
                # 尝试 employee 级别的过滤
                if "employee_id" in clauses and "employee_id" in sql_upper:
                    return clauses["employee_id"]
                return None  # 没有适用列，跳过 RLS

        # V3: attendance 只有 employee_id，没有 dept_id！
        # 优先匹配 employee_id，跳过 dept_id
        if "attendance" in sql_lower:
            if "employee_id" in clauses:
                return clauses["employee_id"]
            return None  # 跳过 RLS 部门过滤

        # customers 没有 dept_id, 有 owner_id / owner_dept_id
        if "customers" in sql_lower:
            if "owner_id" in clauses:
                return clauses["owner_id"]
            if "owner_dept_id" in clauses:
                return clauses["owner_dept_id"]
            return None

        # 默认按 dept_id
        if "dept_id" in clauses:
            return clauses["dept_id"]

        return None

    def _inject_where_clause(self, sql: str, filter_clause: str) -> str:
        """在现有 WHERE 中注入 AND，或添加新的 WHERE"""
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


