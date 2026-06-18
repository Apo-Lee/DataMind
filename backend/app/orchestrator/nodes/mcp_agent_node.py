"""MCP Agent Node — 独立 MCP 工具调用节点

职责：
- 接收 intent_node 的意图 + 实体信息
- 自动选择最匹配的业务工具
- 执行工具调用并返回结构化的多工具结果
- 支持跨数据源工具调用（cross_domain 意图）

设计思路：
原本 sql_node 同时负责 LLM 工具选择 + MCP 调用 + 结果归一化，
MCP Agent Node 将其拆为独立的可编排节点，使得：
1. 可以独立测试工具选择逻辑
2. 可以插入 quality_node 做 SQL 质量校验
3. 支持跨域场景下调用多个 MCP Server
"""

import json
import logging
from typing import Any

from app.mcp_client import get_mcp_client
from app.orchestrator.state import (
    AgentState, AgentContext, SQLResult, IntentType,
)

logger = logging.getLogger(__name__)

# 数据源标签 → 显示名称映射
TAG_NAME_MAP = {"hr": "HR系统", "crm": "CRM系统", "finance": "费控系统", "erp": "ERP系统"}

# 业务意图 → 推荐业务工具映射（引导 LLM 优先使用）
INTENT_TO_PREFERRED_TOOLS = {
    IntentType.direct_query: [],
    IntentType.list_query: ["list_tables"],
    IntentType.aggregation: [],
    IntentType.trend: [],
    IntentType.comparison: [],
    IntentType.ranking: [],
    IntentType.distribution: ["get_employee_distribution", "get_customer_distribution"],
    IntentType.anomaly: [],
    IntentType.root_cause: [],
    IntentType.forecast: [],
    IntentType.drill_down: [],
    IntentType.refinement: [],
    IntentType.cross_domain: [],
    IntentType.greeting: [],
    IntentType.help: [],
    IntentType.unknown: [],
}


def _flatten_rows(data: dict) -> list[dict]:
    """将业务工具返回的嵌套结构拍平成行列表"""
    rows = data.get("rows")
    if rows is not None:
        return rows
    # 业务工具返回自己的结构，尝试找一个 list[dict] 的值
    for v in data.values():
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
            return v
    if data and isinstance(data, dict):
        return [data]
    return []


def _build_tools_text(tools: list[dict]) -> str:
    """将 MCP 工具列表格式化为 LLM 可读的文本"""
    parts = []
    for t in tools:
        name = t["function"]["name"]
        desc = t["function"]["description"]
        params = t["function"]["parameters"]
        props = params.get("properties", {})
        req = params.get("required", [])
        param_lines = []
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "string")
            pdesc = pinfo.get("description", "")
            need = " (必填)" if pname in req else ""
            param_lines.append(f"      - {pname}: {ptype}{need} - {pdesc}")
        ptext = "\n".join(param_lines) if param_lines else "      无参数"
        parts.append(f"  {name}: {desc}\n{ptext}")
    return "\n".join(parts)


SQL_EXEC_PROMPT = """
You are a SQLite SQL expert. Generate ONLY SQL queries.

Data source: {business_tag_name}
Current date: {current_date}
Available tables:
{all_tools}

CRITICAL SQLite rules:
- Use strftime for month extraction, NOT EXTRACT()
- Use date >= 'YYYY-MM-DD' AND date <= 'YYYY-MM-DD' for ranges
- For this month: date between 2026-06-01 and 2026-06-30
- Use GROUP BY + SUM/COUNT/AVG for aggregations
- Use single quotes for strings
- Output ONLY the SQL query, no explanation
"""
async def mcp_agent_node(state: AgentState) -> dict:
    context = state.get("context")
    question = state.get("question", "")
    if context is None:
        return {"mcp_result": SQLResult(status="error", error="Missing context"), "last_error": "Missing context"}
    business_tag = context.business_tag
    client = get_mcp_client()
    client.set_auth(user_role=context.user_role, data_scope=context.user_data_scope, employee_id=context.user_employee_id, dept_id=context.user_dept_id)
    tools = client.get_tools(business_tag)
    if not tools:
        return {"mcp_result": SQLResult(status="error", error="No MCP server"), "last_error": "No tools"}
    tools_text = _build_tools_text(tools)
    tag_name = TAG_NAME_MAP.get(business_tag, business_tag)
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt = SQL_EXEC_PROMPT.replace("{business_tag_name}", tag_name).replace("{all_tools}", tools_text).replace("{current_date}", current_date)
    # Step 1: list tables and schema
    table_result = await client.call_tool(business_tag, 'list_tables', {})
    schema_info = ''
    if table_result.get('success'):
        tbls = table_result.get('data', {}).get('tables', [])
        if tbls:
            schema_info = 'Tables: ' + str(tbls) + '. '
            for t in tbls[:2]:
                d = await client.call_tool(business_tag, 'describe_table', {'table_name': t})
                if d.get('success'):
                    schema_info += str(t) + ': ' + str(d.get('data', {})) + '. '
    # Step 2: Generate SQL via LLM
    from app.core.llm_client import llm_client
    sql_prompt = prompt + chr(10) + chr(10) + 'Schema: ' + schema_info + chr(10) + chr(10) + 'User: ' + question + chr(10) + chr(10) + 'Generate ONLY the SQL query:'
    llm_result = await llm_client.chat([{"role": "system", "content": sql_prompt}])
    content = llm_result.get("content", "").strip()
    import re
    m = re.search(r'SELECT .+?(?:;|$)', content, re.IGNORECASE | re.DOTALL)
    if not m:
        m = re.search(r'```sql\n(.+?)```', content, re.DOTALL)
    if not m:
        m = re.search(r'```\n(.+?)```', content, re.DOTALL)
    if m:
        sql = m.group(0).strip().rstrip(';')
        result = await client.call_tool(business_tag, 'execute_sql', {'sql': sql, 'limit': 500})
        if result.get('success'):
            import pandas as pd
            rows = result.get('data', {}).get('rows', [])
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            return {'mcp_result': SQLResult(status='success', sql=sql, df=df, rows_affected=len(df))}
        return {'mcp_result': SQLResult(status='error', error=result.get('error','exec failed')), 'last_error': 'SQL exec failed'}
    return {'mcp_result': SQLResult(status='error', error='No SQL: ' + content[:200]), 'last_error': 'No SQL generated'}