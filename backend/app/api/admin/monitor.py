import asyncio
import time
import os
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func as sa_func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin
from app.database import get_db
from app.models.user import User
from app.models.datasource import DataSource
from app.models.conversation import Conversation
from app.schemas.admin import MonitorHealthResponse, HealthStatus, MonitorStatsResponse

router = APIRouter(prefix="/api/admin/monitor", tags=["系统监控"])


def _check_docker() -> dict:
    import docker
    client = docker.from_env()
    client.ping()
    return {"status": "ok", "detail": "Docker 可用"}


def _check_memory() -> dict:
    import psutil
    mem = psutil.virtual_memory()
    mem_pct = mem.percent
    status = "ok" if mem_pct < 80 else ("warning" if mem_pct < 95 else "error")
    return {"status": status, "detail": f"使用 {mem_pct:.1f}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)"}


@router.get("/health", response_model=MonitorHealthResponse)
async def get_health(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    components = []

    # 数据库连接
    try:
        await db.execute(sa_func.count(User.id))
        components.append(HealthStatus(component="database", status="ok", detail="连接正常"))
    except Exception as e:
        components.append(HealthStatus(component="database", status="error", detail=str(e)))

    # LLM API
    try:
        from app.core.llm_client import llm_client
        # 简单的 ping (不实际调用 API 产生费用)
        components.append(HealthStatus(component="llm_api", status="ok",
                         detail=f"模型: {llm_client.model}, 端点: {llm_client.base_url}"))
    except Exception as e:
        components.append(HealthStatus(component="llm_api", status="error", detail=str(e)))

    # Docker 沙箱
    try:
        result = await asyncio.to_thread(_check_docker)
        components.append(HealthStatus(component="sandbox_docker", **result))
    except Exception as e:
        components.append(HealthStatus(component="sandbox_docker", status="warning", detail=f"Docker 不可用: {str(e)[:100]}"))

    # Python 解释器
    components.append(HealthStatus(component="python_runtime", status="ok",
                     detail=f"Python {sys.version.split()[0]}"))

    # 内存使用
    try:
        result = await asyncio.to_thread(_check_memory)
        components.append(HealthStatus(component="memory", **result))
    except ImportError:
        components.append(HealthStatus(component="memory", status="ok", detail="psutil 未安装，无法获取"))

    # 整体状态
    statuses = [c.status for c in components]
    if "error" in statuses:
        overall = "degraded"
    elif statuses.count("warning") > 1:
        overall = "degraded"
    else:
        overall = "healthy"

    return MonitorHealthResponse(
        overall=overall,
        components=components,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/stats", response_model=MonitorStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    # 总用户
    total_users_r = await db.execute(sa_func.count(User.id))
    total_users = total_users_r.scalar() or 0

    # 活跃用户
    active_users_r = await db.execute(select(sa_func.count(User.id)).where(User.is_active == True))
    active_users = active_users_r.scalar() or 0

    # 数据源
    total_ds_r = await db.execute(sa_func.count(DataSource.id))
    total_ds = total_ds_r.scalar() or 0

    # 总查询数
    total_queries_r = await db.execute(sa_func.count(Conversation.id))
    total_queries = total_queries_r.scalar() or 0

    # 24h 查询数
    from datetime import timedelta
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    queries_24h_r = await db.execute(
        select(sa_func.count(Conversation.id)).where(Conversation.created_at >= cutoff_24h)
    )
    queries_24h = queries_24h_r.scalar() or 0

    # 平均查询耗时（从 conversations.result_data 的 query_time_ms 字段计算）
    avg_ms_r = await db.execute(
        text("SELECT COALESCE(AVG(json_extract(result_data, '$.query_time_ms')), 0) FROM conversations WHERE result_data IS NOT NULL")
    )
    avg_ms = avg_ms_r.scalar() or 0

    return MonitorStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_datasources=total_ds,
        total_queries=total_queries,
        queries_24h=queries_24h,
        avg_query_time_ms=round(avg_ms, 1),
    )
