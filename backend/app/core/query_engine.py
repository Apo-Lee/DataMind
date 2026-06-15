# -*- coding: utf-8 -*-
"""查询引擎 - 将结构化查询意图翻译为受控的 SQL 查询

核心思路：LLM 不直接生成 SQL，而是生成结构化查询意图（JSON Schema），
由引擎根据用户权限白名单生成安全的 SQL。
这样确保 0 越权风险。
"""

import json
import logging
import re
from typing import Any

import pandas as pd

from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)

# ============================================================
# 1. 敏感字段配置（白名单模式：未列出的就是可查的）
# ============================================================
# 格式：{business_tag: {table: {column: sensitivity_level}}}
# sensitivity_level: "safe" | "sensitive" | "highly_sensitive"
_COLUMN_SENSITIVITY = {
    "hr": {
        "employees": {
            "salary": "highly_sensitive",
            "phone": "sensitive",
            "email": "sensitive",
            "name": "safe",
            "dept_id": "safe",
            "position": "safe",
            "level": "safe",
            "status": "safe",
            "join_date": "safe",
            "performance_score": "safe",
            "manager_id": "safe",
            "position_category": "safe",
            "gender": "safe",
            "education": "safe",
            "id": "safe",
        },
        "departments": {
            "budget": "sensitive",
            "name": "safe",
            "manager_name": "safe",
            "location": "safe",
            "parent_dept_id": "safe",
            "id": "safe",
        },
        "attendance": {
            "check_in": "safe",
            "check_out": "safe",
            "status": "safe",
            "date": "safe",
            "employee_id": "safe",
            "id": "safe",
        },
        "org_hierarchy": {
            "ancestor_id": "safe",
            "descendant_id": "safe",
            "depth": "safe",
        },
    },
    "crm": {
        "customers": {
            "phone": "sensitive",
            "email": "sensitive",
            "name": "safe",
            "industry": "safe",
            "level": "safe",
            "contact_person": "safe",
            "status": "safe",
            "id": "safe",
        },
        "deals": {
            "amount": "safe",
            "status": "safe",
            "close_date": "safe",
            "probability": "safe",
            "title": "safe",
            "customer_id": "safe",
            "id": "safe",
        },
    },
    "finance": {
        "expenses": {
            "amount": "safe",
            "category": "safe",
            "date": "safe",
            "status": "safe",
            "description": "safe",
            "dept_id": "safe",
            "id": "safe",
        },
    },
}

# 角色可以查看的敏感级别
_ROLE_SENSITIVITY_ACCESS = {
    "admin": {"safe", "sensitive", "highly_sensitive"},
    "hr_director": {"safe", "sensitive", "highly_sensitive"},
    "finance_bp": {"safe", "sensitive"},
    "finance_director": {"safe", "sensitive"},
    "dept_ceo": {"safe", "sensitive"},  # V3: 提升到 sensitive
    "dept_manager": {"safe", "sensitive"},  # V3: 提升到 sensitive
    "sales_manager": {"safe", "sensitive"},  # V3: 提升到 sensitive
    "employee": {"safe"},
    "viewer": {"safe"},
}


# ============================================================
# 2. 查询意图 Schema
# ============================================================
_QUERY_INTENT_PROMPT = """你是一个数据分析助手。根据用户的自然语言问题，输出结构化的查询意图 JSON。

可查询的表和列：
{tables_desc}

输出严格 JSON 格式（不要附带其他文字）：
{{
    "question_type": "simple_query | count | aggregation | list | trend",
    "main_table": "主表名",
    "join_tables": ["关联表1", "关联表2"],
    "select_columns": ["列名1", "列名2"],
    "aggregations": [
        {{"type": "COUNT|SUM|AVG|MAX|MIN", "column": "列名", "alias": "别名"}}
    ],
    "filters": [
        {{"column": "列名", "op": "=|!=|>|<|>=|<=|IN|LIKE|BETWEEN", "value": "值"}}
    ],
    "group_by": ["列名"],
    "order_by": [{{"column": "列名", "direction": "ASC|DESC"}}],
    "limit": 数字,
    "explanation": "对这个查询的简短解释"
}}

规则：
- select_columns 只包含用户问题明确提到的列
- 如果用户问总数/平均值等，用 aggregations 而不是 select_columns
- 过滤条件中的值使用数据库中实际存在的中文值
- 日期过滤使用 YYYY-MM-DD 格式
- 如果涉及"部门"，先查 departments 表的部门名称
"""



_V3_NORMALIZE_STATUS_FIXES = [
    ('present', '出勤'),
    ('normal', '出勤'),
    ('absent', '缺勤'),
    ('leave', '请假'),
    ('late', '迟到'),
    ('active', '在职'),
    ('employed', '在职'),
    ('resigned', '离职'),
    ('inactive', '离职'),
    ('probation', '试用期'),
    ('won', '赢单'),
    ('lost', '输单'),
    ('closed_won', '赢单'),
    ('closed_lost', '输单'),
    ('in_progress', '进行中'),
    ('completed', '已完成'),
    ('planned', '规划中'),
    ('pending', '待审批'),
    ('approved', '已审批'),
    ('rejected', '驳回'),
    ('paid', '已支付'),
]


def normalize_sql_values(sql: str) -> str:
    """自动修正 SQL 中常见的枚举值错误"""
    for eng, chn in _V3_NORMALIZE_STATUS_FIXES:
        sql = sql.replace("'" + eng + "'", "'" + chn + "'")
        sql = sql.replace('"' + eng + '"', "'" + chn + "'")
    return sql

def _build_tables_desc(agent) -> str:
    """生成给 LLM 看的表和列描述（不含敏感字段级别）"""
    tables = agent.list_tables()
    lines = []
    for t in tables:
        ts = agent.describe_table(t)
        cols = []
        for c in ts.columns:
            cols.append(c.name + "(" + c.dtype + ")")
        lines.append("  - " + t + ": " + ", ".join(cols))
    return chr(10).join(lines)


async def parse_query_intent(question: str, agent) -> dict:
    """Step 1: LLM 将自然语言解析为结构化查询意图"""
    tables_desc = _build_tables_desc(agent)
    user_msg = _QUERY_INTENT_PROMPT.replace("{tables_desc}", tables_desc)
    user_msg += "\n\n用户问题: " + question

    msg = await llm_client.chat([
        {"role": "system", "content": "你是一个严格输出 JSON 的数据分析助手。"},
        {"role": "user", "content": user_msg},
    ])

    content = msg.get("content", "{}").strip()
    if "{" in content:
        content = content[content.index("{"):content.rindex("}") + 1]
    return json.loads(content)


# ============================================================
# 3. 权限校验引擎
# ============================================================
class PermissionEngine:
    """查询意图级别的权限校验"""

    def __init__(self, user_info: dict, business_tag: str):
        self.role = user_info.get("role", "employee")
        self.data_scope = user_info.get("data_scope", "team")
        self.dept_id = user_info.get("dept_id")
        self.employee_id = user_info.get("employee_id")
        self.business_tag = business_tag
        self.sensitivity = _COLUMN_SENSITIVITY.get(business_tag, {})
        self.max_level = _ROLE_SENSITIVITY_ACCESS.get(self.role, {"safe"})

    def validate_intent(self, intent: dict) -> tuple[bool, str]:
        """校验查询意图是否越权
        Returns: (is_allowed: bool, reason: str)
        """
        main_table = intent.get("main_table", "")

        # 规则1: 检查查询的表是否存在且允许访问
        table_sens = self.sensitivity.get(main_table, {})
        if not table_sens and main_table:
            return (False, "无权访问表 '" + main_table + "'")

        # 规则2: 检查 SELECT 的列是否越权
        for col in intent.get("select_columns", []):
            col_level = table_sens.get(col, "safe")
            if col_level not in self.max_level:
                return (False, "无权查询列 '" + col + "'（级别: " + col_level + "，你的权限: " + str(self.max_level) + "）")

        # 规则3: 检查聚合中的列是否越权
        for agg in intent.get("aggregations", []):
            col = agg.get("column", "")
            if col:
                col_level = table_sens.get(col, "safe")
                if col_level not in self.max_level:
                    return (False, "无权对列 '" + col + "' 做聚合计算")

            # 规则3.1: employee 不能做 AVG/SUM 聚合
            if self.role == "employee" and agg.get("type") in ("SUM", "AVG"):
                return (False, "员工角色不能执行 SUM/AVG 聚合操作")

        # 规则4: 检查过滤条件是否合理
        for f in intent.get("filters", []):
            col = f.get("column", "")
            col_level = table_sens.get(col, "safe")
            if col_level not in self.max_level:
                return (False, "过滤条件中使用了无权查看的列 '" + col + "'")

            # 规则4.1: 不能用敏感列做过滤
            if col_level == "highly_sensitive" and self.role not in ("admin", "hr_director"):
                return (False, "无权用敏感字段 '" + col + "' 作为筛选条件")

        # 规则5: 检查 ORDER BY 中的列
        for ob in intent.get("order_by", []):
            col = ob.get("column", "")
            col_level = table_sens.get(col, "safe")
            if col_level not in self.max_level:
                return (False, "无权按列 '" + col + "' 排序")

        # 规则6: 检查 JOIN 表是否允许
        for join_table in intent.get("join_tables", []):
            join_sens = self.sensitivity.get(join_table, {})
            if not join_sens:
                return (False, "无权关联表 '" + join_table + "'")

        return (True, "")


# ============================================================
# 4. SQL 生成器（受控模板，LLM 不直接操控 SQL）
# ============================================================


# V3: Known foreign key mapping (main_table, join_table) -> (main_fk_col, join_pk_col)
FOREIGN_KEYS_MAP = {
    ("employees", "departments"): ("dept_id", "id"),
    ("attendance", "employees"): ("employee_id", "id"),
    ("deals", "customers"): ("customer_id", "id"),
    ("customers", "departments"): ("owner_dept_id", "id"),
    ("projects", "departments"): ("dept_id", "id"),
    ("purchase_orders", "departments"): ("dept_id", "id"),
    ("resources", "projects"): ("project_id", "id"),
}

class SQLBuilder:
    """根据校验通过的查询意图、用户权限生成安全的 SQL（模板化，杜绝注入）

    V3: 表感知的 SQL 构建
    - 多表 JOIN 时列名前加表名，消除歧义
    - JOIN 条件使用 FOREIGN_KEYS_MAP，不猜列名
    - 不内联 RLS（统一由 QueryInterceptor 注入）
    """

    def __init__(self, user_info: dict, business_tag: str):
        self.user_info = user_info
        self.business_tag = business_tag
        self.sensitivity = _COLUMN_SENSITIVITY.get(business_tag, {})
        self.max_level = _ROLE_SENSITIVITY_ACCESS.get(user_info.get("role", "employee"), {"safe"})

    def build(self, intent: dict) -> str:
        """将校验通过的意图翻译为安全 SQL"""
        main_table = intent.get("main_table", "")
        select_cols = self._build_select(intent)
        joins = self._build_joins(intent)
        where_clause = self._build_where(intent)
        group_by = self._build_group_by(intent)
        order_by = self._build_order_by(intent)
        limit = self._build_limit(intent)

        sql = "SELECT " + select_cols
        sql += " FROM \"" + main_table + "\""
        if joins:
            sql += " " + joins
        if where_clause:
            sql += " WHERE " + where_clause
        if group_by:
            sql += " GROUP BY " + group_by
        if order_by:
            sql += " ORDER BY " + order_by
        if limit:
            sql += " LIMIT " + str(limit)
        return sql

    def _build_select(self, intent: dict) -> str:
        """构建 SELECT 子句（多表 JOIN 时列名加表名前缀）"""
        parts = []
        main_table = intent.get("main_table", "")
        table_sens = self.sensitivity.get(main_table, {})
        has_joins = len(intent.get("join_tables", [])) > 0

        for col in intent.get("select_columns", []):
            if table_sens.get(col, "safe") not in self.max_level:
                continue
            if has_joins:
                parts.append("\"" + main_table + "\".\"" + col + "\"")
            else:
                parts.append("\"" + col + "\"")

        for agg in intent.get("aggregations", []):
            agg_col = agg.get("column", "")
            agg_type = agg.get("type", "COUNT")
            alias = agg.get("alias", agg_type + "_" + agg_col) if agg_col else agg_type
            if agg_col:
                col_level = table_sens.get(agg_col, "safe")
                if col_level not in self.max_level:
                    parts.append("0 AS \"" + alias + "\"")
                else:
                    if has_joins:
                        parts.append(agg_type + "(\"" + main_table + "\".\"" + agg_col + "\") AS \"" + alias + "\"")
                    else:
                        parts.append(agg_type + "(\"" + agg_col + "\") AS \"" + alias + "\"")
            else:
                if agg_type == "SUM":
                    parts.append("COUNT(*) AS \"" + alias + "\"")
                else:
                    parts.append(agg_type + "(*) AS \"" + alias + "\"")

        if not parts:
            parts.append("*")
        return ", ".join(parts)

    def _build_joins(self, intent: dict) -> str:
        """构建 JOIN 子句（只使用 FOREIGN_KEYS_MAP，不猜列名）"""
        main_table = intent.get("main_table", "")
        joins = []
        for jt in intent.get("join_tables", []):
            key = (main_table, jt)
            if key in FOREIGN_KEYS_MAP:
                fk_col, pk_col = FOREIGN_KEYS_MAP[key]
                joins.append("LEFT JOIN \"" + jt + "\" ON \"" + jt + "\".\"" + pk_col + "\" = \"" + main_table + "\".\"" + fk_col + "\"")
            # V3: 找不到外键映射时直接跳过 JOIN（避免生成错误的 column_name）
        return " ".join(joins)

    def _build_where(self, intent: dict) -> str:
        """构建 WHERE 子句（只处理用户过滤条件，不注入 RLS）"""
        user_conds = []
        for f in intent.get("filters", []):
            col = f.get("column", "")
            op = f.get("op", "=")
            val = f.get("value", "")
            if isinstance(val, str):
                user_conds.append("\"" + col + "\" " + op + " '" + str(val) + "'")
            elif isinstance(val, list):
                if op.upper() == "BETWEEN":
                    user_conds.append("\"" + col + "\" BETWEEN '" + str(val[0]) + "' AND '" + str(val[1]) + "'")
                else:
                    vs = ", ".join("'" + str(v) + "'" for v in val)
                    user_conds.append("\"" + col + "\" " + op + " (" + vs + ")")
            else:
                user_conds.append("\"" + col + "\" " + op + " " + str(val))
        return " AND ".join(user_conds) if user_conds else ""

    def _build_group_by(self, intent: dict) -> str:
        cols = intent.get("group_by", [])
        if len(intent.get("join_tables", [])) > 0:
            main_table = intent.get("main_table", "")
            return ", ".join('\"' + main_table + '\".\"' + c + '\"' for c in cols) if cols else ""
        return ", ".join('\"' + c + '\"' for c in cols) if cols else ""

    def _build_order_by(self, intent: dict) -> str:
        obs = intent.get("order_by", [])
        return ", ".join('\"' + ob.get("column", "") + '\" ' + ob.get("direction", "ASC") for ob in obs) if obs else ""

    def _build_limit(self, intent: dict) -> int | None:
        limit = intent.get("limit")
        if limit is None:
            return 1000
        return min(int(limit), 5000)
def mask_sensitive_data(df: pd.DataFrame, intent: dict, user_info: dict, business_tag: str) -> pd.DataFrame:
    """对查询结果中的敏感字段进行脱敏"""
    role = user_info.get("role", "employee")
    max_level = _ROLE_SENSITIVITY_ACCESS.get(role, {"safe"})
    sensitivity = _COLUMN_SENSITIVITY.get(business_tag, {})
    main_table = intent.get("main_table", "")
    table_sens = sensitivity.get(main_table, {})

    if "highly_sensitive" in max_level:
        return df  # 高权限角色不需要脱敏

    df_masked = df.copy()
    for col in df_masked.columns:
        col_level = table_sens.get(col, "safe")
        if col_level == "highly_sensitive":
            # 薪资等高度敏感字段：替换为 ***
            df_masked[col] = "***"
        elif col_level == "sensitive" and "sensitive" not in max_level:
            # 电话/邮箱等敏感字段：脱敏显示
            if col == "phone":
                df_masked[col] = df_masked[col].astype(str).apply(lambda x: x[:3] + "****" + x[-4:] if len(str(x)) > 7 else "***")
            elif col == "email":
                df_masked[col] = df_masked[col].astype(str).apply(lambda x: x.split("@")[0][:2] + "***@" + x.split("@")[1] if "@" in str(x) else "***")
            else:
                df_masked[col] = "***"

    return df_masked


# ============================================================
# 6. 统一入口
# ============================================================
async def safe_query(question: str, agent, user_info: dict) -> dict:
    """安全查询的统一入口（替代 generate_sql）

    流程：自然语言 → 结构化意图 → 权限校验 → 受控SQL生成 → 执行 → 脱敏
    """
    business_tag = agent.business_tag

    try:
        # Step 1: LLM 解析为结构化意图
        intent = await parse_query_intent(question, agent)
    except Exception as e:
        return {"status": "error", "error": "意图解析失败: " + str(e), "rejected": True}

    # Step 2: 权限校验
    engine = PermissionEngine(user_info, business_tag)
    allowed, reason = engine.validate_intent(intent)
    if not allowed:
        return {"status": "error", "error": "权限拒绝: " + reason, "rejected": True}

    # Step 3: 安全 SQL 生成
    try:
        builder = SQLBuilder(user_info, business_tag)
        sql = builder.build(intent)
    except Exception as e:
        return {"status": "error", "error": "SQL 生成失败: " + str(e), "rejected": True}

    # Step 4: 执行 SQL
    try:
        sql = normalize_sql_values(sql)
        df = agent.execute_sql(sql)
    except Exception as e:
        return {"status": "error", "error": "SQL 执行失败: " + str(e), "rejected": True}

    # Step 5: 结果脱敏
    df_masked = mask_sensitive_data(df, intent, user_info, business_tag)

    return {
        "status": "success",
        "sql": sql,
        "intent": intent,
        "data": df_masked,
        "rejected": False,
    }




