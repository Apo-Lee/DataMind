"""RBAC 权限校验依赖 + 统一数据源访问检查 (V2.5)"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import or_

from app.models.user import User, UserRole
from app.models.datasource import DataSource, DataSourcePermission
from app.core.auth import get_current_user, get_role_str
from app.agents.factory import agent_factory
from app.core.row_level_security import RowLevelSecurityEngine


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role if isinstance(current_user.role, str) else current_user.role.value
    if role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def require_role(*roles: UserRole):
    """工厂函数: 返回检查指定角色的依赖"""
    role_values = {r.value for r in roles}
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role if isinstance(current_user.role, str) else current_user.role.value
        if user_role not in role_values:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
        return current_user
    return role_checker


async def check_datasource_access(user: User, datasource_id: str, db: AsyncSession) -> DataSource:
    """统一的数据源访问权限检查 (A1)

    检查逻辑：
    1. admin → 直接放行
    2. 非admin → 遍历 DataSourcePermission 检查 role/user/dept 三级授权
    """
    ds_result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id)
    )
    ds = ds_result.scalar_one_or_none()
    if ds is None or not ds.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在或已停用")

    user_role = get_role_str(user)
    if user_role == UserRole.admin.value:
        return ds

    # 非admin: 检查 role / user / dept 三级授权
    perm_result = await db.execute(
        select(DataSourcePermission).where(
            DataSourcePermission.datasource_id == datasource_id,
            DataSourcePermission.can_query == True,
        )
    )
    perms = perm_result.scalars().all()
    has_access = False
    for p in perms:
        if p.grant_type == "role" and p.grant_target == user_role:
            has_access = True
            break
        if p.grant_type == "user" and p.grant_target == user.id:
            has_access = True
            break
        if p.grant_type == "dept" and user.dept_id is not None and str(user.dept_id) == p.grant_target:
            has_access = True
            break

    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该数据源")

    return ds


async def get_accessible_datasources(user: User, db: AsyncSession) -> list[DataSource]:
    """获取用户可访问的所有数据源列表"""
    user_role = get_role_str(user)
    if user_role == UserRole.admin.value:
        result = await db.execute(select(DataSource).where(DataSource.is_active == True))
    else:
        user_dept = str(user.dept_id) if user.dept_id is not None else None
        conditions = [
            (DataSourcePermission.grant_type == "role") & (DataSourcePermission.grant_target == user_role),
            (DataSourcePermission.grant_type == "user") & (DataSourcePermission.grant_target == user.id),
        ]
        if user_dept:
            conditions.append(
                (DataSourcePermission.grant_type == "dept") & (DataSourcePermission.grant_target == user_dept)
            )
        result = await db.execute(
            select(DataSource).distinct()
            .join(DataSourcePermission, DataSource.id == DataSourcePermission.datasource_id)
            .where(
                DataSourcePermission.can_query == True,
                DataSource.is_active == True,
                or_(*conditions),
            )
        )
    return list(result.scalars().all())


async def get_agent_with_rls(user: User, datasource_id: str, db: AsyncSession):
    """获取 Agent 并注入行级安全范围 (A1: 统一入口)

    先检查权限，再创建 RLS 引擎并注入 Agent。
    """
    ds = await check_datasource_access(user, datasource_id, db)
    agent = agent_factory.get_or_create(ds)
    rls_engine = RowLevelSecurityEngine(user, ds, db)
    rls_scope = await rls_engine.compute_data_scope()
    agent.set_rls_scope(rls_scope)
    return agent, ds
