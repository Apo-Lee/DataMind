"""数据源 & 权限表模型 (V2 增强版)"""
# WHY: DataSourcePermission 增加 grant_type/grant_target/row_filter_scope
#      DataSource 增加 is_system 字段
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

import enum


class DatabaseType(str, enum.Enum):
    mysql = "mysql"
    postgresql = "postgresql"
    sqlite = "sqlite"
    mssql = "mssql"


class DataSource(Base):
    __tablename__ = "datasources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    db_type: Mapped[DatabaseType] = mapped_column(String(10), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    db_name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    business_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # V2: 系统预定义数据源，不可删除
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    permissions: Mapped[list["DataSourcePermission"]] = relationship(
        "DataSourcePermission", back_populates="datasource", cascade="all, delete-orphan"
    )


class DataSourcePermission(Base):
    """数据源级权限 (V2 增强版) — 支持按角色/用户/部门授权"""
    __tablename__ = "datasource_permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )
    # V2: 泛化授权方式
    grant_type: Mapped[str] = mapped_column(String(20), nullable=False, default="role")
    # "role" → grant_target = role值; "user" → grant_target = user_id; "dept" → grant_target = dept_id
    grant_target: Mapped[str] = mapped_column(String(50), nullable=False)
    can_query: Mapped[bool] = mapped_column(Boolean, default=True)
    row_filter_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # None=使用用户默认data_scope; 指定则覆盖 (self_only/team/dept/dept_and_sub/all)

    datasource: Mapped["DataSource"] = relationship("DataSource", back_populates="permissions")
