"""审计日志 API (V2)"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin
from app.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.admin import AuditLogResponse

router = APIRouter(prefix="/api/admin/audit-logs", tags=["审计日志"])


@router.get("", response_model=dict)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    username: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    count_query = select(sa_func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if username:
        query = query.where(AuditLog.username.ilike(f"%{username}%"))
        count_query = count_query.where(AuditLog.username.ilike(f"%{username}%"))

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    total_r = await db.execute(count_query)
    total = total_r.scalar() or 0

    items = result.scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [AuditLogResponse.model_validate(item).model_dump() for item in items],
    }


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="日志不存在")
    return log
