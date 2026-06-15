"""数据权限分配 API (V2) — admin 管理用户的数据访问范围"""
import json
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit_log
from app.core.auth import get_current_user
from app.core.permissions import require_admin
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.datasource import DataSource, DataSourcePermission
from app.models.permission import RowLevelPolicy
from app.models.user import User
from app.schemas.admin import UserPermissionUpdate, DatasourcePermissionUpdate

router = APIRouter(prefix="/api/admin/permissions", tags=["数据权限"])


# ---- 用户数据权限 ----

@router.get("/users")
async def list_user_permissions(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """列出所有用户的数据权限配置"""
    result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    result = []
    for u in users:
        extra_dept_ids: list = []
        with suppress(Exception):
            extra_dept_ids = json.loads(u.extra_dept_ids) if u.extra_dept_ids else []
        result.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role.value if hasattr(u.role, 'value') else str(u.role),
            "employee_id": u.employee_id,
            "dept_id": u.dept_id,
            "data_scope": u.data_scope.value if hasattr(u.data_scope, 'value') else str(u.data_scope),
            "extra_dept_ids": extra_dept_ids,
            "is_active": u.is_active,
            "source": u.source,
        })
    return result


@router.put("/users/{user_id}")
async def update_user_permission(
    user_id: str,
    body: UserPermissionUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """修改用户的数据权限范围"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.data_scope is not None:
        user.data_scope = body.data_scope
    if body.extra_dept_ids is not None:
        user.extra_dept_ids = json.dumps(body.extra_dept_ids) if body.extra_dept_ids else None

    # V2: 审计日志（记录操作人，即 admin）
    await write_audit_log(
        db, _admin, AuditAction.permission_changed,
        resource_type="user", resource_id=user_id,
        detail={"target_user": user.username, "data_scope": body.data_scope, "extra_dept_ids": body.extra_dept_ids},
    )

    await db.commit()
    await db.refresh(user)
    extra_dept_ids_safe: list = []
    with suppress(Exception):
        extra_dept_ids_safe = json.loads(user.extra_dept_ids) if user.extra_dept_ids else []
    return {
        "id": user.id,
        "data_scope": user.data_scope.value if hasattr(user.data_scope, 'value') else str(user.data_scope),
        "extra_dept_ids": extra_dept_ids_safe,
    }


# ---- 数据源权限矩阵 ----

@router.get("/datasources")
async def list_datasource_permissions(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """列出所有数据源的权限配置"""
    ds_result = await db.execute(select(DataSource).order_by(DataSource.name))
    datasources = ds_result.scalars().all()

    result = []
    for ds in datasources:
        perm_result = await db.execute(
            select(DataSourcePermission).where(DataSourcePermission.datasource_id == ds.id)
        )
        perms = perm_result.scalars().all()
        result.append({
            "datasource_id": ds.id,
            "datasource_name": ds.name,
            "business_tag": ds.business_tag,
            "is_system": ds.is_system,
            "grants": [
                {
                    "grant_type": p.grant_type,
                    "grant_target": p.grant_target,
                    "can_query": p.can_query,
                    "row_filter_scope": p.row_filter_scope,
                }
                for p in perms
            ],
        })
    return result


@router.put("/datasources/{datasource_id}")
async def update_datasource_permissions(
    datasource_id: str,
    body: DatasourcePermissionUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """全量替换数据源的权限配置"""
    ds_result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    ds = ds_result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 删除旧权限
    old_perms = (await db.execute(
        select(DataSourcePermission).where(DataSourcePermission.datasource_id == datasource_id)
    )).scalars().all()
    for p in old_perms:
        await db.delete(p)

    # 创建新权限
    for grant in body.grants:
        db.add(DataSourcePermission(
            datasource_id=datasource_id,
            grant_type=grant.grant_type,
            grant_target=grant.grant_target,
            can_query=grant.can_query,
            row_filter_scope=grant.row_filter_scope,
        ))

    await write_audit_log(
        db, _admin, AuditAction.permission_changed,
        resource_type="datasource", resource_id=datasource_id,
        detail={"grants_count": len(body.grants), "action": "replace_all"},
    )

    await db.commit()
    return {"datasource_id": datasource_id, "grants": len(body.grants)}


# ---- RLS 行级安全策略管理 (P2-6) ----

@router.get("/rls-policies")
async def list_rls_policies(
    datasource_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """列出 RLS 行级安全策略，可按数据源筛选"""
    query = select(RowLevelPolicy).order_by(RowLevelPolicy.priority.desc())
    if datasource_id:
        query = query.where(RowLevelPolicy.datasource_id == datasource_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/rls-policies", status_code=201)
async def create_rls_policy(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """创建 RLS 行级安全策略"""
    if not body.get("datasource_id") or not body.get("policy_type") or not body.get("policy_config"):
        raise HTTPException(status_code=400, detail="datasource_id, policy_type, policy_config 为必填字段")
    policy = RowLevelPolicy(
        datasource_id=body["datasource_id"],
        policy_type=body["policy_type"],
        policy_config=body["policy_config"],
        target_table=body.get("target_table"),
        priority=body.get("priority", 0),
        is_active=body.get("is_active", True),
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    await write_audit_log(
        db, _admin, AuditAction.permission_changed,
        resource_type="rls_policy", resource_id=policy.id,
        detail={"datasource_id": body["datasource_id"], "policy_type": body["policy_type"], "action": "create"},
    )
    return policy


@router.put("/rls-policies/{policy_id}")
async def update_rls_policy(
    policy_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """更新 RLS 行级安全策略"""
    result = await db.execute(select(RowLevelPolicy).where(RowLevelPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    for field in ("policy_type", "target_table", "priority", "is_active"):
        if field in body:
            setattr(policy, field, body[field])
    if "policy_config" in body:
        policy.policy_config = body["policy_config"]
    await db.commit()
    await db.refresh(policy)
    await write_audit_log(
        db, _admin, AuditAction.permission_changed,
        resource_type="rls_policy", resource_id=policy_id,
        detail={"datasource_id": policy.datasource_id, "policy_type": policy.policy_type, "action": "update"},
    )
    return policy


@router.delete("/rls-policies/{policy_id}", status_code=204)
async def delete_rls_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """删除 RLS 行级安全策略"""
    result = await db.execute(select(RowLevelPolicy).where(RowLevelPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    await write_audit_log(
        db, _admin, AuditAction.permission_changed,
        resource_type="rls_policy", resource_id=policy_id,
        detail={"datasource_id": policy.datasource_id, "policy_type": policy.policy_type, "action": "delete"},
    )
    await db.delete(policy)
    await db.commit()
