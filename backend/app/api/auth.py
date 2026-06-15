"""认证 API 路由 (V2: 含审计日志 + 登录速率限制)"""

import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_role_str,
    verify_password,
)
from app.core.audit import write_audit_log
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["认证"])

# V2.6: 内存登录速率限制（滑动窗口，每 IP 60 秒内最多 5 次）
# NOTE: 多实例部署时无效，生产环境应换 Redis / slowapi
_login_attempts: dict[str, list[float]] = {}


def _check_rate_limit(ip: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # 清理过期记录
    attempts = [t for t in attempts if now - t < window_seconds]
    _login_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return False
    attempts.append(now)
    return True


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="登录尝试过于频繁，请 1 分钟后再试")
    
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已停用")

    # V2: 记录登录审计日志
    await write_audit_log(
        db, user, AuditAction.login,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    role_str = get_role_str(user)
    return TokenResponse(
        access_token=create_access_token(user.id, role_str, user.employee_id, user.dept_id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌类型错误")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    await write_audit_log(
        db, user, AuditAction.login,
        detail={"via": "refresh"},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    role_str = get_role_str(user)
    return TokenResponse(
        access_token=create_access_token(user.id, role_str, user.employee_id, user.dept_id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
