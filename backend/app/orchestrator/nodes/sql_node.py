import json, logging, time
from typing import Any

from app.mcp_client import get_mcp_client
from app.orchestrator.state import AgentState, AgentContext, SQLResult, IntentType

logger = logging.getLogger(__name__)

MCP_SYSTEM_PROMPT = """你是一个企业数据分析助手。通过 MCP (Model Context Protocol) 工具查询业务数据。

可用的数据源类型：HR系统、CRM系统、费控系统、ERP系统
当前数据源: {business_tag_name}

可用工具：
{all_tools}

规则:
1. 优先使用专用业务工具（如 get_department_budget、get_employee_distribution）回答常见问题
2. 如无合适业务工具，用 list_tables 查看表结构再用 query_data 工具
3. 聚合统计（人数、总额、平均）使用 aggregations 参数
4. 过滤条件的值使用中文实际值（如状态用"在职"/"离职"，出服用"出勤"/"请假"）
5. 日期格式使用 YYYY-MM-DD
6. 必须使用工具调用获取数据，不要自行编造数据
7. 不要查询你没有权限查看的敏感列
"""

async def sql_node(state: AgentState) -> dict:
    context: AgentContext | None = state.get("context")
    question = state.get("question", "")

    if context is None:
        return {"sql_result": SQLResult(status="error", error="缺少 Agent 上下文"), "last_error": "Missing context"}

    business_tag = context.business_tag
    client = get_mcp_client()
    client.set_auth(
        user_role=context.user_role,
        data_scope=context.user_data_scope,
        employee_id=context.user_employee_id,
        dept_id=context.user_dept_id,
    )

    tools = client.get_tools(business_tag)
    if not tools:
        return {"sql_result": SQLResult(status="error", error=f"MCP Server not found: {business_tag}"), "last_error": "No tools"}

    tag_name_map = {"hr": "HR系统", "crm": "CRM系统", "finance": "费控系统", "erp": "ERP系统"}

    all_tools_text = []
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
        all_tools_text.append(f"  {name}: {desc}\n{ptext}")

    tools_text = "\n".join(all_tools_text)
    prompt = MCP_SYSTEM_PROMPT.replace("{business_tag_name}", tag_name_map.get(business_tag, business_tag)).replace("{all_tools}", tools_text)

    user_msg = (
        f"【数据源】{tag_name_map.get(business_tag, business_tag)} ({business_tag})\n"
        f"【你的角色】{context.user_role}, 数据范围={context.user_data_scope}\n"
        f"【部门】{context.user_dept_name} (ID={context.user_dept_id})\n\n"
        f"用户问题: {question}\n\n"
        f"请选择合适的工具查询数据。"
    )

    from app.core.llm_client import llm_client
    llm_result = await llm_client.chat(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_msg},
        ],
        tools=tools,
    )

    tool_calls = llm_result.get("tool_calls")
    if not tool_calls:
        content = llm_result.get("content", "")
        logger.warning(f"LLM 未选择工具: {content[:200]}")
        return {
            "sql_result": SQLResult(
                status="error",
                error=f"无法生成查询: {content[:200] if content else 'LLM 未返回工具调用'}",
                error_type="IntentError",
            ),
            "last_error": "No tool call from LLM",
        }

    # execute first tool call
    tc = tool_calls[0]
    tool_name = tc["function"]["name"]
    args_raw = tc["function"]["arguments"]
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            args = {}
    else:
        args = args_raw

    start_time = time.time()
    logger.info(f"MCP Agent calling: {tool_name}({args})")
    result = await client.call_tool(business_tag, tool_name, args)
    sql_elapsed_ms = round((time.time() - start_time) * 1000)

    if not result.get("success"):
        error_msg = result.get("error", f"{tool_name} 执行失败")
        logger.warning(f"MCP Tool 执行失败: {error_msg}")
        return {
            "sql_result": SQLResult(status="error", error=error_msg, error_type="QueryError"),
            "last_error": error_msg,
        }

    data = result.get("data", {})
    # normalize rows from various tool result formats
    rows = data.get("rows", None)
    if rows is None:
        # business tools return their own structure e.g. {"departments":[...], "employee_counts":[...]}
        # flatten into a display-friendly list
        for v in data.values():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                rows = v
                break
        if rows is None:
            rows = [data] if data else []

    import pandas as pd
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    sql = data.get("sql", f"[MCP] {tool_name}")

    return {
        "sql_result": SQLResult(
            status="success",
            sql=sql,
            df=df,
            rows_affected=len(df),
            execution_time_ms=sql_elapsed_ms,
        ),
    }
