"""
app/mcp_servers/registry.py — MCP Server 注册表
管理所有 MCP Server 的生命周期和路由
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

_servers: dict[str, object] = {}


def init_mcp_servers():
    """初始化并注册所有 MCP Server"""
    from .hr_server import HRMCPServer
    from .crm_server import CRMMCPServer
    from .finance_server import FinanceMCPServer
    from .erp_server import ERPMCPServer

    _servers["hr"] = HRMCPServer()
    _servers["crm"] = CRMMCPServer()
    _servers["finance"] = FinanceMCPServer()
    _servers["erp"] = ERPMCPServer()
    logger.info(f"MCP Servers initialized: {list(_servers.keys())}")


def get_server(business_tag: str):
    """按业务标签获取 MCP Server"""
    return _servers.get(business_tag)


def list_all_servers():
    """获取所有 MCP Server 信息"""
    return {tag: {"name": s.name, "tools": [t.name for t in s._tools.values()]} for tag, s in _servers.items()}


def build_mcp_router() -> APIRouter:
    """构建统一的 MCP API 路由"""
    if not _servers:
        init_mcp_servers()

    router = APIRouter(prefix="/api/mcp", tags=["MCP Servers"])

    @router.get("/servers")
    async def list_servers():
        return list_all_servers()

    @router.get("/{tag}/tools")
    async def list_tools(tag: str):
        server = get_server(tag)
        if not server:
            return {"error": f"Server not found: {tag}"}
        return {"tools": server.list_tools()}

    @router.post("/{tag}/execute")
    async def execute_tool(tag: str, body: dict):
        server = get_server(tag)
        if not server:
            return {"success": False, "error": f"Server not found: {tag}"}
        tool_name = body.get("tool", "")
        args = body.get("args", {})
        # 支持通过 body 传递权限上下文
        auth_ctx = body.get("auth", {})
        if auth_ctx:
            from app.mcp_servers.base_sql import MCPAuth
            server.set_auth(MCPAuth(
                user_role=auth_ctx.get("role", "employee"),
                data_scope=auth_ctx.get("scope", "self_only"),
                employee_id=auth_ctx.get("employee_id"),
                dept_id=auth_ctx.get("dept_id"),
            ))
        result = await server.execute_tool(tool_name, args)
        return result.model_dump()

    @router.get("/{tag}/health")
    async def health(tag: str):
        server = get_server(tag)
        if not server:
            return {"status": "error", "error": f"Server not found: {tag}"}
        return {"status": "ok", "name": server.name, "tag": tag}

    # 合并各个 Server 的路由
    for tag, server in _servers.items():
        router.include_router(server.get_routes())

    return router


def dispose_all():
    """释放所有 MCP Server 的资源"""
    for tag, server in _servers.items():
        try:
            server.dispose()
        except Exception as e:
            logger.warning(f"Dispose {tag} failed: {e}")
    _servers.clear()
