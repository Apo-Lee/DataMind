"""
app/orchestrator/mcp_node.py — MCP Agent Node
使用 MCP Server 替代直接 SQL 的工具节点
"""
import json, logging
from typing import Any
from app.mcp_client import get_mcp_client


logger = logging.getLogger(__name__)

# MCP 工具的 System Prompt
MCP_SYSTEM_PROMPT = """你是一个企业数据分析助手。通过 MCP (Model Context Protocol) 工具查询业务数据。

可用的数据源和工具：
{all_tools}

规则:
1. 优先使用 query 工具进行结构化查询（支持聚合、过滤、分组、排序）
2. 业务专用工具(如 get_sales_pipeline/get_project_summary) 能更高效地回答特定业务问题
3. 如果不知道表结构，先用 list_tables 查看
4. 过滤条件的值使用中文实际值（如状态用"在职"/"出勤"/"赢单"）
5. 日期格式使用 YYYY-MM-DD
6. 必须使用工具调用获取数据，不要自行编造数据
"""


async def mcp_agent_node(user_question: str, business_tag: str) -> dict:
    """使用 MCP 工具的 Agent 节点
    
    流程:
    1. 获取 MCP 工具定义
    2. LLM 选择工具和参数
    3. 执行工具
    4. 返回结果
    """
    from app.core.llm_client import llm_client
    
    client = get_mcp_client()
    tools = client.get_tools(business_tag)
    
    if not tools:
        return {"status": "error", "error": f"MCP Server not found: {business_tag}"}
    
    # 构建 tool definitions 的文本描述
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
            param_lines.append(f"      - {pname}: {ptype}{need} — {pdesc}")
        ptext = "\n".join(param_lines) if param_lines else "      无参数"
        all_tools_text.append(f"  📦 {name}: {desc}\n{ptext}")
    
    tools_text = "\n".join(all_tools_text)
    prompt = MCP_SYSTEM_PROMPT.replace("{all_tools}", tools_text)
    
    user_msg = (
        f"【数据源】{business_tag}\n"
        f"【用户问题】{user_question}\n\n"
        f"请选择合适的工具查询数据。"
    )
    
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
        return {"status": "error", "error": f"LLM 未选择工具: {content[:200]}"}
    
    # 执行工具调用
    results = []
    for tc in tool_calls:
        tool_name = tc["function"]["name"]
        args_raw = tc["function"]["arguments"]
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
        else:
            args = args_raw
        
        logger.info(f"MCP Agent calling: {tool_name}({args})")
        result = await client.call_tool(business_tag, tool_name, args)
        results.append({
            "tool": tool_name,
            "args": args,
            "result": result,
        })
        
        if not result.get("success"):
            return {"status": "error", "error": f"工具 {tool_name} 执行失败: {result.get('error')}"}
    
    return {
        "status": "success",
        "results": results,
        "business_tag": business_tag,
    }
