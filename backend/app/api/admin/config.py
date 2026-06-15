"""系统配置 API (V2)"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit_log
from app.core.permissions import require_admin
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.system_config import SystemConfig
from app.schemas.admin import SystemConfigItem, SystemConfigUpdate

router = APIRouter(prefix="/api/admin/configs", tags=["系统配置"])


@router.get("", response_model=list[SystemConfigItem])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    result = await db.execute(select(SystemConfig).order_by(SystemConfig.key))
    return result.scalars().all()


@router.get("/{key}", response_model=SystemConfigItem)
async def get_config(
    key: str,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return config


@router.put("/{key}", response_model=SystemConfigItem)
async def update_config(
    key: str,
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    is_new = config is None
    if is_new:
        config = SystemConfig(key=key, value=body.value, value_type=body.value_type or "string")
        db.add(config)
    else:
        config.value = body.value
        if body.value_type is not None:
            config.value_type = body.value_type
    config.updated_by = _admin.username

    await write_audit_log(
        db, _admin, AuditAction.config_changed,
        resource_type="system_config", resource_id=key,
        detail={"action": "create" if is_new else "update", "value": body.value, "value_type": body.value_type},
    )

    await db.commit()
    await db.refresh(config)
    return config
