# -*- coding: utf-8 -*-
"""查询引擎 V3 — 最终稳定版本
"""
import json, logging
from typing import Any
import pandas as pd
from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)

_COLUMN_SENSITIVITY = {
    "hr": {
        "employees": {
            "salary": "highly_sensitive", "phone": "sensitive", "email": "sensitive",
            "name": "safe", "dept_id": "safe", "position": "safe",
            "level": "safe", "status": "safe", "join_date": "safe",
            "performance_score": "safe", "manager_id": "safe",
            "position_category": "safe", "gender": "safe", "education": "safe",
            "id": "safe",
        },
        "departments": {
            "budget": "sensitive", "name": "safe", "manager_name": "safe",
            "location": "safe", "parent_dept_id": "safe", "id": "safe",
        },
        "attendance": {
            "check_in": "safe", "check_out": "safe", "status": "safe",
            "date": "safe", "employee_id": "safe", "id": "safe",
        },
        "org_hierarchy": {"ancestor_id": "safe", "descendant_id": "safe", "depth": "safe"},
    },
    "crm": {
        "customers": {
            "phone": "sensitive", "email": "sensitive",
            "name": "safe", "industry": "safe", "level": "safe",
            "contact_person": "safe", "created_date": "safe",
            "owner_id": "safe", "owner_dept_id": "safe", "id": "safe",
        },
        "deals": {
            "amount": "safe", "status": "safe", "close_date": "safe",
            "probability": "safe", "title": "safe", "customer_id": "safe",
            "stage": "safe", "created_date": "safe",
            "expected_close_date": "safe", "owner_id": "safe",
            "dept_id": "safe", "id": "safe",
        },
        "follow_ups": {
            "type": "safe", "content": "safe", "next_action": "safe",
            "date": "safe", "customer_id": "safe", "employee_id": "safe",
            "id": "safe",
        },
        "sales_targets": {
            "target_amount": "safe", "achieved_amount": "safe",
            "year": "safe", "quarter": "safe",
            "employee_id": "safe", "dept_id": "safe", "id": "safe",
        },
    },
    "finance": {
        "expenses": {
            "amount": "safe", "category": "safe", "date": "safe",
            "status": "safe", "description": "safe", "dept_id": "safe",
            "employee_id": "safe", "approver_id": "safe",
            "expense_type": "safe", "project_code": "safe", "id": "safe",
        },
        "budgets": {
            "amount": "safe", "used": "safe", "remaining_adj": "safe",
            "year": "safe", "quarter": "safe", "category": "safe",
            "budget_type": "safe", "dept_id": "safe",
            "approver_id": "safe", "id": "safe",
        },
        "cost_centers": {"name": "safe", "budget_total": "safe", "budget_remaining": "safe", "fiscal_year": "safe", "dept_id": "safe", "id": "safe"},
        "travel_expenses": {"departure_date": "safe", "return_date": "safe", "destination": "safe", "purpose": "safe", "transport_fee": "safe", "hotel_fee": "safe", "meal_fee": "safe", "other_fee": "safe", "expense_id": "safe", "employee_id": "safe", "id": "safe"},
    },
    "erp": {
        "inventory": {"item_code": "safe", "name": "safe", "category": "safe", "quantity": "safe", "unit_price": "safe", "warehouse": "safe", "dept_id": "safe", "min_stock": "safe", "max_stock": "safe", "supplier_name": "safe", "id": "safe"},
        "projects": {"name": "safe", "project_code": "safe", "status": "safe", "budget": "safe", "actual_cost": "safe", "start_date": "safe", "end_date": "safe", "priority": "safe", "dept_id": "safe", "manager_id": "safe", "id": "safe"},
        "project_dept": {"project_id": "safe", "dept_id": "safe", "role": "safe", "id": "safe"},
        "purchase_orders": {"item_name": "safe", "quantity": "safe", "unit_price": "safe", "total_amount": "safe", "status": "safe", "order_date": "safe", "expected_date": "safe", "dept_id": "safe", "requester_id": "safe", "approver_id": "safe", "id": "safe"},
        "resources": {"project_id": "safe", "employee_id": "safe", "role": "safe", "allocation_pct": "safe", "daily_cost": "safe", "start_date": "safe", "end_date": "safe", "id": "safe"},
    },
}

_ROLE_SENSITIVITY_ACCESS = {
    "admin": {"safe", "sensitive", "highly_sensitive"},
    "hr_director": {"safe", "sensitive", "highly_sensitive"},
    "finance_bp": {"safe", "sensitive"}, "finance_director": {"safe", "sensitive"},
    "dept_ceo": {"safe", "sensitive"}, "dept_manager": {"safe", "sensitive"},
    "sales_manager": {"safe", "sensitive"},
    "employee": {"safe"}, "viewer": {"safe"},
}

_QUERY_INTENT_PROMPT = """你是一个数据分析助手。根据用户问题，输出结构化的查询意图 JSON。

用户上下文（必须使用真实值，禁止使用占位符）：
- 当前用户角色: {user_role}
- 用户 employee_id: {user_employee_id}
- 用户部门 dept_id: {user_dept_id}
- 数据范围: {user_scope}

可查询的表和列：
{tables_desc}

输出严格 JSON：
{{"question_type":"count|aggregation|list|trend","main_table":"主表名","join_tables":["关联表"],"select_columns":["列名"],"aggregations":[{{"type":"COUNT|SUM|AVG|MAX|MIN","column":"列名","alias":"别名"}}],"filters":[{{"column":"列名","op":"=|>=|<=|!=","value":"值"}}],"group_by":["列名"],"order_by":[{{"column":"列名","direction":"ASC|DESC"}}],"limit":数字}}

规则：
1. 列名不加表名前缀
2. select_columns 中不允许 strftime/CASE/聚合函数
3. 过滤值用中文（在职/出勤/赢单/已审批）
4. 日期用 YYYY-MM-DD
5. 不要用 "dept_id" 过滤 departments 表（departments 表没有 dept_id 只有 id）
6. attendance 表没有 dept_id 和 name 列
7. 统计某部门人数时直接用 main_table 过滤 dept_id，不需要 JOIN departments
8. 【重要】filter 中的 value 必须使用用户上下文中的真实数字ID，禁止使用占位符如 "当前用户ID"、"?", "当前部门ID" 等文本字符串
9. 【重要】用户角色为 employee 时，必须根据用户上下文使用自己的 employee_id 过滤数据
10. 【重要】查询薪资/工资/薪酬相关的列时，检查列是否包含 salary 关键字，如果用户角色不是 admin/hr_director/finance_director，则拒绝查询
11. 【重要】filter 的 value 只能是具体的字符串或数字值，不能使用子查询(subquery/SELECT)，不能使用 IN 子句以外的SQL语法
"""


def _build_tables_desc(agent) -> str:
    tables = agent.list_tables()
    lines = []
    for t in tables:
        ts = agent.describe_table(t)
        cols = [c.name + "(" + c.dtype + ")" for c in ts.columns]
        lines.append("  - " + t + ": " + ", ".join(cols))
    return "\n".join(lines)


def _build_intent_prompt(question: str, tables_desc: str, user_info: dict | None = None) -> str:
    """构建意图识别提示，注入用户上下文"""
    if user_info:
        role = str(user_info.get("role", "employee"))
        emp_id = str(user_info.get("employee_id", "未知"))
        dept_id = str(user_info.get("dept_id", "未知"))
        scope = str(user_info.get("data_scope", "unknown"))
        context = (
            "用户上下文（必须使用下面的真实值）:\n"
            "- 当前角色: " + role + "\n"
            "- employee_id: " + emp_id + "\n"
            "- dept_id: " + dept_id + "\n"
            "- 数据范围: " + scope + "\n\n"
        )
    else:
        context = ""
    prompt_body = _QUERY_INTENT_PROMPT.replace("{tables_desc}", tables_desc)
    return context + prompt_body + "\n\n用户问题: " + question


async def parse_query_intent(question: str, agent, user_info: dict | None = None) -> dict:
    tables_desc = _build_tables_desc(agent)
    msg = await llm_client.chat([
        {"role": "system", "content": "只输出 JSON 对象，无任何其他文字。"},
        {"role": "user", "content": _build_intent_prompt(question, tables_desc, user_info)},
    ])
    content = msg.get("content", "{}").strip()
    if "{" in content:
        content = content[content.index("{"):content.rindex("}") + 1]
    intent = json.loads(content)

    # 后处理：修复占位符值为真实用户ID
    if user_info:
        emp_id = str(user_info.get("employee_id", ""))
        dept_id = str(user_info.get("dept_id", ""))
        placeholders = {
            "当前用户ID": emp_id,
            "当前用户employee_id": emp_id,
            "当前部门ID": dept_id,
            "当前角色ID": emp_id,
            "当前用户": emp_id,
            "{user_employee_id}": emp_id,
            "{user_dept_id}": dept_id,
        }
        for f in intent.get("filters", []):
            val = f.get("value", "")
            if val in placeholders and placeholders[val]:
                f["value"] = placeholders[val]

    tables = [intent.get("main_table", "")] + intent.get("join_tables", [])
    for key in ("select_columns", "group_by", "order_by"):
        items = intent.get(key, [])
        if isinstance(items, list):
            cleaned = []
            for c in items:
                col = c.get("column", c) if isinstance(c, dict) else c
                for t in tables:
                    if isinstance(col, str) and col.startswith(t + "."):
                        col = col[len(t) + 1:]
                        break
                if isinstance(col, str) and "(" not in col and "CASE" not in col:
                    cleaned.append(col if not isinstance(c, dict) else {**c, "column": col})
            intent[key] = cleaned if (isinstance(items[0], str) if items else True) else items

    for agg in intent.get("aggregations", []):
        col = agg.get("column", "")
        for t in tables:
            if col.startswith(t + "."):
                col = col[len(t) + 1:]
                break
        if col == "*" and agg.get("type") != "COUNT":
            agg["type"] = "COUNT"
        if any(kw in col for kw in ["(", "CASE"]):
            col = ""
        agg["column"] = col

    new_filters = []
    for f in intent.get("filters", []):
        v = f.get("value", "")
        # 修复：子查询占位符（LLM 可能错误地生成 subquery 文本）
        if isinstance(v, str) and ("subquery" in v.lower() or "SELECT" in v.upper()):
            continue  # 跳过子查询过滤，改成不加这个过滤条件
        if f.get("op", "").upper() == "BETWEEN" and isinstance(v, str) and "," in v:
            vs = [x.strip() for x in v.split(",")]
            if len(vs) == 2:
                new_filters.append({"column": f["column"], "op": ">=", "value": vs[0]})
                new_filters.append({"column": f["column"], "op": "<=", "value": vs[1]})
                continue
        new_filters.append(f)
    intent["filters"] = new_filters

    # 意图级安全检查：检测薪资相关查询
    _salary_keywords = ["薪资", "工资", "薪酬", "工资表", "salary", "薪资表", "薪水"]
    contains_salary_q = any(kw in question for kw in _salary_keywords)
    
    # 如果问题提到薪资，检查用户权限
    if contains_salary_q:
        main_table = intent.get("main_table", "")
        ts = _COLUMN_SENSITIVITY.get(agent.business_tag, {}).get(main_table, {})
        has_salary_col = "salary" in ts
        if has_salary_col:
            role = user_info.get("role", "employee") if user_info else "employee"
            max_level = _ROLE_SENSITIVITY_ACCESS.get(role, {"safe"})
            if "highly_sensitive" not in max_level:
                # 无论模型是否选择了 salary 列，只要问题涉及薪资且角色无权限，直接拒绝
                raise Exception(f"当前角色({role})无权查询薪资数据")

    return intent


class PermissionEngine:
    def __init__(self, user_info: dict, business_tag: str):
        self.role = user_info.get("role", "employee")
        self.max_level = _ROLE_SENSITIVITY_ACCESS.get(self.role, {"safe"})
        self.sens = _COLUMN_SENSITIVITY.get(business_tag, {})

    def validate_intent(self, intent: dict) -> tuple:
        """默认软拒绝: 自动过滤不可见列，只有当所有列都被过滤时才硬拒绝"""
        ts = self.sens.get(intent.get("main_table", ""), {})
        if not ts:
            return (True, "")
        intent["select_columns"] = [c for c in intent.get("select_columns", [])
                                     if ts.get(c, "safe") in self.max_level]
        intent["aggregations"] = [a for a in intent.get("aggregations", [])
                                    if not a.get("column") or ts.get(a["column"], "safe") in self.max_level]
        intent["filters"] = [f for f in intent.get("filters", [])
                               if ts.get(f["column"], "safe") in self.max_level]
        if not intent["select_columns"] and not intent["aggregations"]:
            return (False, "当前角色无权查看任何列")
        if self.role == "employee":
            for a in intent.get("aggregations", []):
                if a.get("type") in ("SUM", "AVG"):
                    return (False, "员工角色不能做全公司聚合")
        return (True, "")

FK = {
    ("employees", "departments"): ("dept_id", "id"),
    ("attendance", "employees"): ("employee_id", "id"),
    ("deals", "customers"): ("customer_id", "id"),
    ("customers", "departments"): ("owner_dept_id", "id"),
    ("projects", "departments"): ("dept_id", "id"),
    ("purchase_orders", "departments"): ("dept_id", "id"),
    ("resources", "projects"): ("project_id", "id"),
    ("follow_ups", "customers"): ("customer_id", "id"),
    ("sales_targets", "departments"): ("dept_id", "id"),
    ("expenses", "departments"): ("dept_id", "id"),
    ("budgets", "departments"): ("dept_id", "id"),
    ("inventory", "departments"): ("dept_id", "id"),
    ("cost_centers", "departments"): ("dept_id", "id"),
}


class SQLBuilder:
    def __init__(self, user_info: dict, business_tag: str):
        self.tag = business_tag
        self.sens = _COLUMN_SENSITIVITY.get(business_tag, {})
        self.ml = _ROLE_SENSITIVITY_ACCESS.get(user_info.get("role", "employee"), {"safe"})

    def _find_table(self, col: str, mt: str, joins: list[str]) -> str:
        """查找列所属的表（用于 JOIN 时加表名前缀消除歧义）"""
        for t in [mt] + joins:
            ts = self.sens.get(t, {})
            if col in ts:
                return t
        return mt

    def build(self, intent: dict) -> str:
        mt = intent.get("main_table", "")
        joins = intent.get("join_tables", [])
        has_joins = bool(joins)
        gb = intent.get("group_by", [])

        # SELECT
        parts = []
        ts = self.sens.get(mt, {})

        def add_col(col):
            t = self._find_table(col, mt, joins)
            parts.append(('"' + t + '"."' if has_joins else '"') + col + '"')

        for c in intent.get("select_columns", []):
            if c in ts:
                add_col(c)

        for c in gb:
            if c in intent.get("select_columns", []):
                continue
            if c in ts:
                add_col(c)

        for a in intent.get("aggregations", []):
            col, typ, alias = a.get("column", ""), a.get("type", "COUNT"), a.get("alias", "")
            if not alias:
                alias = typ + ("_" + col if col else "")
            if not col:
                parts.append('COUNT(*) AS "' + alias + '"')
            else:
                lev = ts.get(col, "safe")
                if lev not in self.ml:
                    parts.append('0 AS "' + alias + '"')
                else:
                    # 安全检查：确认列在表中存在
                    t = self._find_table(col, mt, joins)
                    _all_cols = set()
                    for _t in [mt] + joins:
                        _ts = self.sens.get(_t, {})
                        _all_cols.update(_ts.keys())
                    if col not in _all_cols:
                        # 列不存在，回退为 COUNT(*)
                        parts.append('COUNT(*) AS "' + alias + '"')
                    else:
                        parts.append(typ + '("' + t + '"."' + col + '") AS "' + alias + '"')

        sql = "SELECT " + (", ".join(parts) if parts else "*") + ' FROM "' + mt + '"'

        # JOIN
        for jt in joins:
            k = (mt, jt)
            if k in FK:
                fk, pk = FK[k]
                sql += ' LEFT JOIN "' + jt + '" ON "' + jt + '"."' + pk + '" = "' + mt + '"."' + fk + '"'

        # WHERE — 精确查找列所属的表
        conds = []
        for f in intent.get("filters", []):
            col, op, val = f["column"], f["op"], str(f["value"])
            t = self._find_table(col, mt, joins)
            pref = ('"' + t + '".' if has_joins else "") + '"' + col + '"'
            conds.append(pref + " " + op + " '" + val.replace("'", "''") + "'")
        if conds:
            sql += " WHERE " + " AND ".join(conds)

        if gb:
            sql += " GROUP BY " + ", ".join('"' + self._find_table(c, mt, joins) + '"."' + c + '"' for c in gb)
        obs = intent.get("order_by", [])
        if obs:
            sql += " ORDER BY " + ", ".join('"' + o["column"] + '" ' + o.get("direction", "ASC") for o in obs)
        lmt = intent.get("limit")
        sql += " LIMIT " + str(1000 if lmt is None else min(int(lmt), 5000))
        return sql


async def mcp_safe_query(question, agent, user_info):
    """MCP ?????"""
    from app.mcp_client import get_mcp_client
    try:
        intent = await parse_query_intent(question, agent, user_info)
    except Exception as e:
        return {"status":"error","error":"\u610f\u56fe\u89e3\u6790\u5931\u8d25:"+str(e),"rejected":True}
    ok, reason = PermissionEngine(user_info, agent.business_tag).validate_intent(intent)
    if not ok:
        return {"status":"error","error":"\u6743\u9650\u62d2\u7edd:"+reason,"rejected":True}
    client = get_mcp_client()
    client.set_auth(user_role=user_info.get("role","employee"),data_scope=user_info.get("data_scope","self_only"),employee_id=user_info.get("employee_id"),dept_id=user_info.get("dept_id"))
    params={
        "main_table":intent.get("main_table",""),
        "select_columns":intent.get("select_columns",[]),
        "aggregations":intent.get("aggregations",[]),
        "filters":intent.get("filters",[]),
        "join_tables":intent.get("join_tables",[]),
        "group_by":intent.get("group_by",[]),
        "order_by":intent.get("order_by",[]),
        "limit":intent.get("limit",100),
    }
    result = await client.query(agent.business_tag, params)
    if not result.get("success"):
        return {"status":"error","error":"MCP\u67e5\u8be2\u5931\u8d25:"+result.get("error",""),"rejected":True}
    import pandas as pd
    df = pd.DataFrame(result["data"].get("rows",[])) if result["data"].get("rows") else pd.DataFrame()
    return {"status":"success","sql":result["data"].get("sql",""),"intent":intent,"data":df,"rejected":False}


def mask_sensitive_data(df, intent, user_info, business_tag):
    role = user_info.get("role", "employee")
    ml = _ROLE_SENSITIVITY_ACCESS.get(role, {"safe"})
    if "highly_sensitive" in ml:
        return df
    sens = _COLUMN_SENSITIVITY.get(business_tag, {}).get(intent.get("main_table", ""), {})
    dm = df.copy()
    for c in dm.columns:
        lv = sens.get(c, "safe")
        if lv == "highly_sensitive":
            dm[c] = "***"
        elif lv == "sensitive" and "sensitive" not in ml:
            dm[c] = "***"
    return dm


async def safe_query(question, agent, user_info):
    try:
        intent = await parse_query_intent(question, agent, user_info)
    except Exception as e:
        return {"status": "error", "error": "意图解析失败: " + str(e), "rejected": True}
    ok, reason = PermissionEngine(user_info, agent.business_tag).validate_intent(intent)
    if not ok:
        return {"status": "error", "error": "权限拒绝: " + reason, "rejected": True}
    try:
        sql = SQLBuilder(user_info, agent.business_tag).build(intent)
    except Exception as e:
        return {"status": "error", "error": "SQL 生成失败: " + str(e), "rejected": True}
    try:
        df = agent.execute_sql(sql)
    except Exception as e:
        return {"status": "error", "error": "SQL 执行失败: " + str(e), "rejected": True}
    return {"status": "success", "sql": sql, "intent": intent, "data": mask_sensitive_data(df, intent, user_info, agent.business_tag), "rejected": False}
