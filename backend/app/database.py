"""数据库引擎 & 会话管理 (V2)"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """创建所有表（开发用，生产用 Alembic）"""
    # 导入所有模型以确保它们被 Base 注册
    from app.models.user import User  # noqa: F401
    from app.models.datasource import DataSource, DataSourcePermission  # noqa: F401
    from app.models.conversation import Conversation, KpiPreference  # noqa: F401
    from app.models.permission import RowLevelPolicy  # noqa: F401
    from app.models.audit_log import AuditLog, HrSyncLog  # noqa: F401
    from app.models.system_config import SystemConfig  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()
