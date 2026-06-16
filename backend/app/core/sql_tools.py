"""SQL Tools — OpenAI Function Calling 风格的 SQL 查询工具

每个 Tool 定义中包含权限约束、RLS 过滤和敏感字段脱敏。
LLM 通过 Tool Calling 调用查询数据，而不是直接操作 SQL。
"""

import json
import logging
import re
from typing import Any

import pandas as pd

from app.agents.base import DataSourceAgent
from app.core.query_engine import _COLUMN_SENSITIVITY, _ROLE_SENSITIVITY_ACCESS

_COLUMN_SEMANTICS = {}

logger = logging.getLogger(__name__)


def _sanitize_sql_value(value: str) -> str:
    """净化 SQL 字符串值，防止注入"""
    return value.replace("'", "''")


def _filter_visible_columns(
    business_tag: str,
    table_name: str,
    role: str,
) -> list[dict]:
    """获取角色在指定表中可见的列列表"""
    sens = _COLUMN_SENSITIVITY.get(business_tag, {})
    table_sens = sens.get(table_name, {})
    max_level = _ROLE_SENSITIVITY_ACCESS.get(role, {"safe"})
    semantics = _COLUMN_SEMANTICS.get(business_tag, {}).get(table_name, {})

    visible = []
    for col, level in table_sens.items():
        if level in max_level:
            visible.append({
                "name": col,
                "type": "TEXT",
                "sensitive": level != "safe",
                "description": semantics.get(col, ""),
            })
    return visible


def _filter_visible_columns_for_role(
    business_tag: str,
    table_name: str,
    role: str,
) -> list[dict]:
    """获取角色在指定表中可见的列列表（供 sql_node 使用）"""
    return _filter_visible_columns(business_tag, table_name, role)


def build_query_tools(
    business_tag: str,
    tables_columns: dict[str, list[dict]],
    role: str,
    data_scope: str,
) -> list[dict]:
    """构建 Function Calling 工具定义"""
    table_descriptions = []
    for tname, cols in tables_columns.items():
        col_desc = ", ".join(
            f"{c['name']}({'🔒' if c['sensitive'] else '✓'}{': ' + c['description'] if c.get('description') else ''})"
            for c in cols
        )
        table_descriptions.append(f"  - {tname}: {col_desc}")

    return [{
        "type": "function",
        "function": {
            "name": "query_data",
            "description": (
                f"查询业务数据（角色={role}，数据范围={data_scope}）。"
                f"支持 SELECT + 过滤/聚合/分组/排序。可用表：\n"
                + "\n".join(table_descriptions)
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "main_table": {
                        "type": "string",
                        "description": "主查询表名",
                        "enum": list(tables_columns.keys()),
                    },
                    "select_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要查询的列名。聚合查询应包含 GROUP BY 列。",
                    },
                    "aggregations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["COUNT", "SUM", "AVG", "MAX", "MIN"]},
                                "column": {"type": "string"},
                                "alias": {"type": "string"},
                            },
                        },
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "op": {"type": "string", "enum": ["=", "!=", ">", "<", ">=", "<=", "IN", "LIKE", "BETWEEN"]},
                                "value": {"type": "string"},
                            },
                        },
                    },
                    "join_tables": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "order_by": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "direction": {"type": "string", "enum": ["ASC", "DESC"]},
                            },
                        },
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回行数上限（默认100，最大5000）",
                        "default": 100,
                    },
                },
                "required": ["main_table", "select_columns"],
            },
        },
    }, {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "查看当前数据源中所有可查询的表及其列结构",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "查看指定表的列结构详情",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "要查看的表名"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_suggest",
            "description": "让LLM根据问题自动建议查询参数，用于复杂场景辅助",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "用户的自然语言问题"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "在受控模式下执行受限的SQL查询（仅SELECT，受RLS约束）",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_where": {"type": "string", "description": "WHERE子句内容，例如 status = '在职' AND dept_id = 1"},
                    "main_table": {"type": "string", "description": "要查询的主表名"},
                    "select_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要查询的列名列表"
                    },
                    "limit": {"type": "integer", "default": 100}
                },
                "required": ["main_table", "select_columns"]
            }
        }
    }
    ]

_FOREIGN_KEYS_MAP = {
    ("employees", "departments"): ("dept_id", "id"),
    ("attendance", "employees"): ("employee_id", "id"),
    ("deals", "customers"): ("customer_id", "id"),
    ("customers", "departments"): ("owner_dept_id", "id"),
    ("projects", "departments"): ("dept_id", "id"),
    ("purchase_orders", "departments"): ("dept_id", "id"),
    ("resources", "projects"): ("project_id", "id"),
}


def _build_safe_sql(
    main_table: str,
    select_columns: list[str],
    aggregations: list[dict] | None = None,
    filters: list[dict] | None = None,
    join_tables: list[str] | None = None,
    group_by: list[str] | None = None,
    order_by: list[dict] | None = None,
    limit: int = 100,
    role: str = "employee",
) -> str:
    """模板化构建安全 SQL（所有值经净化处理，杜绝注入）"""
    aggs = aggregations or []
    flts = filters or []
    joins = join_tables or []
    gb = group_by or []
    ob = order_by or []

    # SELECT
    select_parts = []
    for col in select_columns:
        select_parts.append(f'"{col}"')
    for agg in aggs:
        agg_col = agg.get("column", "")
        agg_type = agg.get("type", "COUNT")
        alias = agg.get("alias", f"{agg_type}_{agg_col}" if agg_col else agg_type)
        if agg_col:
            select_parts.append(f'{agg_type}("{agg_col}") AS "{alias}"')
        else:
            select_parts.append(f'{agg_type}(*) AS "{alias}"')

    if not select_parts:
        select_parts.append("*")

    sql = f"SELECT {', '.join(select_parts)} FROM \"{main_table}\""

    # JOIN
    for jt in joins:
        key = (main_table, jt)
        if key in _FOREIGN_KEYS_MAP:
            fk_col, pk_col = _FOREIGN_KEYS_MAP[key]
            sql += f' LEFT JOIN "{jt}" ON "{jt}"."{pk_col}" = "{main_table}"."{fk_col}"'
        else:
            rkey = (jt, main_table)
            if rkey in _FOREIGN_KEYS_MAP:
                fk2, pk2 = _FOREIGN_KEYS_MAP[rkey]
                sql += f' LEFT JOIN "{jt}" ON "{main_table}"."{fk2}" = "{jt}"."{pk2}"'

    # WHERE
    where_parts = []
    for f in flts:
        col = f.get("column", "")
        op = f.get("op", "=")
        val = f.get("value", "")

        if op.upper() == "BETWEEN":
            vals = [v.strip() for v in val.split(",", 1)]
            if len(vals) == 2:
                where_parts.append(f'"{col}" BETWEEN \'{_sanitize_sql_value(vals[0])}\' AND \'{_sanitize_sql_value(vals[1])}\'')
        elif op.upper() == "IN":
            vals = ", ".join(f"'{_sanitize_sql_value(v.strip())}'" for v in val.split(","))
            where_parts.append(f'"{col}" IN ({vals})')
        elif op.upper() == "LIKE":
            where_parts.append(f'"{col}" LIKE \'{_sanitize_sql_value(val)}\'')
        else:
            where_parts.append(f'"{col}" {op} \'{_sanitize_sql_value(val)}\'')

    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)

    if gb:
        sql += " GROUP BY " + ", ".join(f'"{c}"' for c in gb)
    if ob:
        sql += " ORDER BY " + ", ".join(
            f'"{o["column"]}" {o.get("direction", "ASC")}' for o in ob
        )
    sql += f" LIMIT {min(max(limit, 1), 5000)}"
    return sql


class SQLToolExecutor:
    """SQL 工具执行器 — 在 LangGraph 节点中使用"""

    def __init__(
        self,
        agent: DataSourceAgent,
        rls_engine=None,
        user_role: str = "employee",
        user_info: dict | None = None,
    ):
        self.agent = agent
        self.rls_engine = rls_engine
        self.user_role = user_role
        self.user_info = user_info or {}
        self.business_tag = agent.business_tag

    async def execute_tool(self, tool_name: str, tool_args: dict) -> dict:
        if tool_name == "list_tables":
            return self._handle_list_tables()
        if tool_name == "query_data":
            return await self._handle_query_data(tool_args)
        return {"status": "error", "error": f"未知工具: {tool_name}"}

    def _handle_list_tables(self) -> dict:
        tables = self.agent.list_tables()
        sens = _COLUMN_SENSITIVITY.get(self.business_tag, {})

        result = []
        for t in tables:
            table_sens = sens.get(t, {})
            cols = []
            try:
                schema = self.agent.describe_table(t)
                for c in schema.columns:
                    level = table_sens.get(c.name, "safe")
                    if level in _ROLE_SENSITIVITY_ACCESS.get(self.user_role, {"safe"}):
                        cols.append({
                            "name": c.name,
                            "type": c.dtype,
                            "sensitive": level != "safe",
                        })
            except Exception:
                cols.append({"name": "*", "type": "unknown", "sensitive": False})
            result.append({"table": t, "columns": cols})

        return {"status": "success", "data": {"tables": result}, "sql": "", "columns": []}

    async def _handle_query_data(self, args: dict) -> dict:
        main_table = args.get("main_table", "")
        limit = args.get("limit", 100)

        sql = _build_safe_sql(
            main_table=main_table,
            select_columns=args.get("select_columns", []),
            aggregations=args.get("aggregations"),
            filters=args.get("filters"),
            join_tables=args.get("join_tables"),
            group_by=args.get("group_by"),
            order_by=args.get("order_by"),
            limit=limit,
            role=self.user_role,
        )

        # 注入 RLS
        if self.rls_engine:
            rls_scope = await self.rls_engine.compute_data_scope()
            if rls_scope.get("mode") == "filtered":
                from app.core.query_rewriter import QueryInterceptor
                interceptor = QueryInterceptor(rls_scope)
                try:
                    schema = self.agent.describe_table(main_table)
                    col_names = [c.name for c in schema.columns]
                    interceptor.set_table_columns(main_table, col_names)
                except Exception:
                    pass
                sql = interceptor.rewrite_sql(sql, table_name=main_table)

        logger.info(f"SQL Tool 执行: {sql[:200]}")
        try:
            df = self.agent.execute_sql(sql)
        except Exception as e:
            logger.error(f"SQL 执行失败: {e}")
            return {"status": "error", "error": f"SQL 执行失败: {e}"}

        df_masked = self._mask_data(df)
        columns = list(df_masked.columns)
        records = df_masked.head(500).to_dict(orient="records")

        return {
            "status": "success",
            "data": {"rows": records, "total_rows": len(df_masked), "columns": columns},
            "sql": sql,
            "columns": columns,
        }

    
    def _handle_describe_table(self, args: dict) -> dict:
        """处理 describe_table 查看表结构"""
        table_name = args.get("table_name", "")
        if not table_name:
            return {"status": "error", "error": "?? table_name"}
        try:
            schema = self.agent.describe_table(table_name)
            visible = _filter_visible_columns(self.business_tag, table_name, self.user_role)
            col_names = {c["name"] for c in visible} if visible else set()
            cols = []
            for c in schema.columns:
                if not col_names or c.name in col_names:
                    cols.append({"name": c.name, "type": c.dtype})
            return {"status": "success", "data": {"table": table_name, "columns": cols}}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _handle_query_suggest(self, args: dict) -> dict:
        """处理 query_suggest LLM 建议查询"""
        question = args.get("question", "")
        if not question:
            return {"status": "error", "error": "????"}
        from app.core.llm_client import llm_client
        tables = self.agent.list_tables()
        schema_text = chr(10).join(f"  {t}: {', '.join(c.name for c in self.agent.describe_table(t).columns)}" for t in tables)
        prompt = f"???: {self.business_tag}, ??={self.user_role}\n???:\n{schema_text}\n\n用户问题: {question}\n\n请返回 query_data 工具需要的参数JSON"
        try:
            msg = await llm_client.chat([{"role": "system", "content": "??????????????????"}, {"role": "user", "content": prompt}])
            raw = msg.get("content", "{}")
            if "{" in raw:
                raw = raw[raw.index("{"):raw.rindex("}") + 1]
            params = json.loads(raw)
            return {"status": "success", "data": {"suggestion": params, "note": "?????? query_data"}}
        except Exception as e:
            return {"status": "success", "data": {"suggestion": {"main_table": "", "select_columns": []}, "error": str(e), "note": "??????????????"}}

    async def _handle_execute_sql(self, args: dict) -> dict:
        """处理 execute_sql 受限SQL查询"""
        main_table = args.get("main_table", "")
        select_columns = args.get("select_columns", [])
        sql_where = args.get("sql_where", "")
        limit = min(int(args.get("limit", 100)), 5000)

        if not main_table or not select_columns:
            return {"status": "error", "error": "?? main_table ? select_columns"}

        cols = ", ".join(f'"{c}"' for c in select_columns)
        sql = f"SELECT {cols} FROM \"{main_table}\""
        if sql_where:
            safe_where = sql_where.replace("'", "''")
            sql += f" WHERE {safe_where}"
        sql += f" LIMIT {limit}"

        # RLS injection
        if self.rls_engine:
            rls_scope = await self.rls_engine.compute_data_scope()
            if rls_scope.get("mode") == "filtered":
                from app.core.query_rewriter import QueryInterceptor
                interceptor = QueryInterceptor(rls_scope)
                sql = interceptor.rewrite_sql(sql, table_name=main_table)

        logger.info(f"execute_sql: {sql[:200]}")
        try:
            df = self.agent.execute_sql(sql)
        except Exception as e:
            return {"status": "error", "error": f"SQL ????: {e}"}
        df_masked = self._mask_data(df)
        records = df_masked.head(500).to_dict(orient="records")
        return {"status": "success", "data": {"rows": records, "total_rows": len(df_masked), "columns": list(df_masked.columns)}, "sql": sql}



    def _mask_data(self, df: pd.DataFrame) -> pd.DataFrame:
            sens = _COLUMN_SENSITIVITY.get(self.business_tag, {})
            max_level = _ROLE_SENSITIVITY_ACCESS.get(self.user_role, {"safe"})
            if "highly_sensitive" in max_level:
                return df
            df_masked = df.copy()
            for table_name, table_sens in sens.items():
                for col, level in table_sens.items():
                    if col not in df_masked.columns:
                        continue
                    if level == "highly_sensitive":
                        df_masked[col] = "***"
                    elif level == "sensitive" and "sensitive" not in max_level:
                        if col == "phone":
                            df_masked[col] = df_masked[col].astype(str).apply(
                                lambda x: x[:3] + "****" + x[-4:] if len(str(x)) > 7 else "***"
                            )
                        elif col == "email":
                            df_masked[col] = df_masked[col].astype(str).apply(
                                lambda x: x.split("@")[0][:2] + "***@" + x.split("@")[1]
                                if "@" in str(x) else "***"
                            )
                        else:
                            df_masked[col] = "***"
            return df_masked


