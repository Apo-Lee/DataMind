"""
MCP Client — Agent 通过此客户端调用 MCP Server 的工具
权限上下文通过 contextvar 传递（auth_context.set_user_auth），修复并发竞态
"""
import json, logging
from app.mcp_servers.registry import get_server, init_mcp_servers

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP 客户端 — 进程内调用 MCP Server，支持权限控制"""

    def __init__(self):
        if not get_server("hr"):
            init_mcp_servers()

    def set_auth(self, user_role="employee", data_scope="self_only",
                 employee_id=None, dept_id=None):
        """设置调用者权限上下文（通过 contextvar，不会污染全局）

        原先的循环 srv.set_auth(...) 灌入单例 server 已被移除。
        各 server 的 handler 通过 auth_context.get_user_auth() 读取当前任务的权限。
        """
        from app.core.auth_context import set_user_auth
        set_user_auth(user_role, data_scope, employee_id, dept_id)
        return self

    def get_tools(self, business_tag):
        server = get_server(business_tag)
        if not server:
            return []
        return server.list_tools()

    def get_all_tools(self):
        return {tag: self.get_tools(tag) for tag in ["hr", "crm", "finance", "erp"]}

    async def call_tool(self, business_tag, tool_name, args):
        server = get_server(business_tag)
        if not server:
            return {"success": False, "error": f"MCP Server not found: {business_tag}"}
        result = await server.execute_tool(tool_name, args)
        if not result.success:
            return {"success": False, "error": result.error}
        return {"success": True, "data": result.data}

    async def query(self, business_tag, params):
        return await self.call_tool(business_tag, "query", params)

    async def execute_sql(self, business_tag, sql, limit=100):
        return await self.call_tool(business_tag, "execute_sql", {"sql": sql, "limit": limit})

    async def list_tables(self, business_tag):
        result = await self.call_tool(business_tag, "list_tables", {})
        if result.get("success"):
            return result["data"].get("tables", [])
        return []

    async def describe_table(self, business_tag, table_name):
        result = await self.call_tool(business_tag, "describe_table", {"table_name": table_name})
        return result.get("data", {}) if result.get("success") else {}


_client = None
def get_mcp_client():
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
