"""HR 同步 API (V2)"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import agent_factory
from app.core.audit import write_audit_log
from app.core.hr_sync import sync_hr_to_users
from app.core.permissions import require_admin
from app.database import get_db
from app.models.audit_log import AuditAction, HrSyncLog
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.admin import HrSyncStatusResponse, HrSyncLogResponse

router = APIRouter(prefix="/api/admin/hr-sync", tags=["HR同步"])


@router.post("/trigger")
async def trigger_sync(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """手动触发 HR 数据同步"""
    # 获取 HR 数据源
    hr_result = await db.execute(
        select(DataSource).where(DataSource.business_tag == "hr", DataSource.is_active == True)
    )
    hr_ds = hr_result.scalar_one_or_none()
    if hr_ds is None:
        raise HTTPException(status_code=400, detail="HR 数据源未配置或未激活")

    agent = agent_factory.get_or_create(hr_ds)
    sync_log = await sync_hr_to_users(db, agent)

    await write_audit_log(
        db, _admin, AuditAction.hr_sync,
        resource_type="hr_sync", resource_id=sync_log.id,
        detail={"status": sync_log.status, "created": sync_log.created_users, "updated": sync_log.updated_users, "deactivated": sync_log.deactivated_users},
    )

    return {
        "status": sync_log.status,
        "total_hr_employees": sync_log.total_hr_employees,
        "created_users": sync_log.created_users,
        "updated_users": sync_log.updated_users,
        "deactivated_users": sync_log.deactivated_users,
        "errors": sync_log.errors,
    }


@router.get("/status", response_model=HrSyncStatusResponse)
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """获取最近一次同步状态"""
    result = await db.execute(
        select(HrSyncLog).order_by(HrSyncLog.created_at.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()

    # 获取 HR 数据源员工数
    hr_count = None
    try:
        hr_result = await db.execute(
            select(DataSource).where(DataSource.business_tag == "hr", DataSource.is_active == True)
        )
        hr_ds = hr_result.scalar_one_or_none()
        if hr_ds:
            agent = agent_factory.get_or_create(hr_ds)
            df = await asyncio.to_thread(agent.execute_sql, "SELECT COUNT(*) as cnt FROM employees WHERE status IN ('在职','试用期')")
            if df is not None and not df.empty:
                hr_count = int(df["cnt"].iloc[0])
    except Exception:
        pass

    # 匹配/未匹配 — 使用 SQL COUNT 而非加载全部行
    matched_r = await db.execute(select(sa_func.count(User.id)).where(User.source == "hr_sync", User.is_active == True))
    matched = matched_r.scalar() or 0
    unmatched_r = await db.execute(select(sa_func.count(User.id)).where(User.source == "manual"))
    unmatched = unmatched_r.scalar() or 0

    return HrSyncStatusResponse(
        last_sync_at=latest.completed_at.isoformat() if latest and latest.completed_at else None,
        last_sync_status=latest.status if latest else None,
        hr_employee_count=hr_count,
        matched_users=matched if matched > 0 else None,
        unmatched_users=unmatched if unmatched > 0 else None,
    )


@router.get("/logs", response_model=list[HrSyncLogResponse])
async def get_sync_logs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(HrSyncLog).order_by(HrSyncLog.created_at.desc()).limit(20)
    )
    return result.scalars().all()
