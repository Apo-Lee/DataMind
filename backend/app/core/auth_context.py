# -*- coding: utf-8 -*-
"""auth_context.py — 基于 contextvars 的请求级权限上下文

替代原先的 self._auth 全局单例模式，利用 contextvar 的 per-task 语义
天然隔离并发请求的权限上下文（修复 P0 竞态 bug）。

用法：
    # 入口处（API handler / Agent node）设置一次
    set_user_auth_from_user(current_user)
    # 或手动构造
    set_user_auth(role="employee", data_scope="self_only", employee_id=1, dept_id=3)

    业务 handler 通过 get_user_auth() 自动读取当前请求的 MCPAuth。
"""

from contextvars import ContextVar
from app.mcp_servers.base_sql import MCPAuth
from app.models.user import User

# 默认 MCPAuth → employee / self_only（最小权限）
_user_auth_ctx: ContextVar[MCPAuth] = ContextVar("user_auth", default=MCPAuth())


def get_user_auth() -> MCPAuth:
    """获取当前请求/任务的权限上下文。"""
    return _user_auth_ctx.get()


def set_user_auth_from_user(user: User) -> None:
    """从已认证的 User ORM 对象创建 MCPAuth 并注入当前任务上下文。"""
    role = user.role.value if hasattr(user.role, "value") else user.role
    scope = user.data_scope.value if hasattr(user.data_scope, "value") else user.data_scope
    auth = MCPAuth(
        user_role=role,
        data_scope=scope,
        employee_id=user.employee_id,
        dept_id=user.dept_id,
    )
    _user_auth_ctx.set(auth)


def set_user_auth(
    user_role: str = "employee",
    data_scope: str = "self_only",
    employee_id: int | None = None,
    dept_id: int | None = None,
) -> None:
    """直接设置 MCPAuth（兼容旧调用点）。"""
    auth = MCPAuth(
        user_role=user_role,
        data_scope=data_scope,
        employee_id=employee_id,
        dept_id=dept_id,
    )
    _user_auth_ctx.set(auth)
