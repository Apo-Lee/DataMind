"""JWT 令牌创建 & 验证"""
# WHY: 使用 hashlib pbkdf2_hmac 替代 passlib bcrypt，兼容 Windows 环境

import hashlib
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 密码哈希"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    return salt.hex() + "$" + dk.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        salt_hex, dk_hex = hashed_password.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), bytes.fromhex(salt_hex), 600000)
        return dk.hex() == dk_hex
    except Exception:
        return False


def get_role_str(user: User) -> str:
    """兼容 user.role 为 str 或 Enum"""
    return user.role if isinstance(user.role, str) else getattr(user.role, "value", str(user.role))


def create_access_token(user_id: str, role: str, employee_id: int | None = None, dept_id: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire, "type": "access"}
    if employee_id is not None:
        payload["emp_id"] = employee_id
    if dept_id is not None:
        payload["dept_id"] = dept_id
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")
    # 验证令牌类型 — 防止 refresh_token 被用于 API 访问
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌类型错误")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    return user
