"""DataMind FastAPI 入口 (V2)"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# WHY: 使用统一的 logging 替代 print，便于生产环境日志采集
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
)
logger = logging.getLogger("datamind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import init_db
    await init_db()
    try:
        from app.seed import seed
        await seed()
    except Exception as e:
        logger.warning(f"Seed 失败（可能非首次启动）: {e}")

    # 预编译 LangGraph（可选提速）
    try:
        from app.orchestrator.graph.builder import get_compiled_graph
        logger.info("预编译 LangGraph Agent 图...")
        get_compiled_graph()
    except Exception as e:
        logger.warning(f"LangGraph 预编译跳过: {e}")
    yield


app = FastAPI(title="DataMind", version="0.2.0", lifespan=lifespan)

from app.config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.datasources import router as datasources_router
from app.api.dashboard import router as dashboard_router
from app.api.query import router as query_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(datasources_router)
app.include_router(dashboard_router)
app.include_router(query_router)


# LangGraph Agent 路由（新增）
from app.api.agent import router as agent_router
app.include_router(agent_router)

# V2: 管理后台 API (admin only)
from app.api.admin.monitor import router as monitor_router
from app.api.admin.audit_logs import router as audit_logs_router
from app.api.admin.hr_sync import router as hr_sync_router
from app.api.admin.config import router as config_router
from app.api.admin.permissions import router as permissions_router

app.include_router(monitor_router)
app.include_router(audit_logs_router)
app.include_router(hr_sync_router)
app.include_router(config_router)
app.include_router(permissions_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}

