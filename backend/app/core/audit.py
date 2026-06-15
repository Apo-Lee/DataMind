"""审计日志中间件 & 工具函数 (V2)"""
import asyncio
import functools
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User


async def write_audit_log(
    db: AsyncSession,
    user: User | None,
    action: AuditAction,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    **kwargs,
):
    """写入一条审计日志"""
    action_str = action.value if isinstance(action, AuditAction) else action
    display_name = user.display_name if user else "system"

    # 避免 datetime 冲突: 使用 naive datetime (SQLite 有时区问题)
    log = AuditLog(
        user_id=user.id if user else None,
        username=display_name,
        action=action_str,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=kwargs.get("ip_address"),
        user_agent=kwargs.get("user_agent"),
    )
    db.add(log)
    # 不 commit — 由调用方负责


def audit_action(action: AuditAction):
    """装饰器：自动记录 API 操作的审计日志

    用法:
        @router.post("/ask")
        @audit_action(AuditAction.query_executed)
        async def ask_question(...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            # 审计日志由调用方手动调用 write_audit_log
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
