"""
app/mcp_servers/__init__.py — DataMind MCP Server 注册表
"""

import json, logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPToolParam(BaseModel):
    """MCP 工具参数的属性定义"""
    type: str = "string"
    description: str = ""
    enum: list[str] | None = None
    default: Any = None


class MCPTool(BaseModel):
    """MCP 工具定义"""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class MCPResult(BaseModel):
    """MCP 执行结果"""
    success: bool = True
    data: Any = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class BaseMCPServer:
    """MCP Server 基类 — 每个数据源一个实例"""

    def __init__(self, name: str, business_tag: str):
        self.name = name
        self.business_tag = business_tag
        self._tools: dict[str, MCPTool] = {}
        self._tool_handlers: dict[str, callable] = {}

    def register_tool(self, tool: MCPTool, handler: callable):
        self._tools[tool.name] = tool
        self._tool_handlers[tool.name] = handler

    def list_tools(self) -> list[dict]:
        """返回 OpenAI/Anthropic 兼容的 tool 定义列表"""
        result = []
        for t in self._tools.values():
            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": t.parameters,
                        "required": t.required,
                    },
                },
            })
        return result

    async def execute_tool(self, tool_name: str, args: dict) -> MCPResult:
        handler = self._tool_handlers.get(tool_name)
        if not handler:
            return MCPResult(success=False, error=f"Unknown tool: {tool_name}")
        try:
            if asyncio.iscoroutinefunction(handler):
                data = await handler(args)
            else:
                data = handler(args)
            return MCPResult(success=True, data=data)
        except Exception as e:
            logger.error(f"MCP tool {tool_name} failed: {e}")
            return MCPResult(success=False, error=str(e))

    # ——— FastAPI 路由方法 ———
    def get_routes(self):
        """返回 {path: (method, handler)} 字典"""
        from fastapi import APIRouter
        router = APIRouter(prefix=f"/mcp/{self.business_tag}", tags=[f"MCP-{self.name}"])

        @router.get("/tools")
        async def list_mcp_tools():
            return {"tools": self.list_tools()}

        @router.post("/execute")
        async def execute_mcp_tool(body: dict):
            tool_name = body.get("tool", "")
            args = body.get("args", {})
            result = await self.execute_tool(tool_name, args)
            return result.model_dump()

        @router.get("/health")
        async def health():
            return {"status": "ok", "server": self.name, "tag": self.business_tag}

        return router


import asyncio  # noqa: E402 (needed for iscoroutinefunction check above)
