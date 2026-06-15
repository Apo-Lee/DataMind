"""操作审计日志 & HR 同步日志模型 (V2)"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

import enum


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    query_executed = "query_executed"
    sql_executed = "sql_executed"
    permission_changed = "permission_changed"
    hr_sync = "hr_sync"
    config_changed = "config_changed"
    user_created = "user_created"
    user_modified = "user_modified"
    user_deactivated = "user_deactivated"
    data_exported = "data_exported"
    dashboard_viewed = "dashboard_viewed"


class AuditLog(Base):
    """操作审计日志"""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HrSyncLog(Base):
    """HR 同步日志"""
    __tablename__ = "hr_sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / running / success / failed
    total_hr_employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_users: Mapped[int] = mapped_column(Integer, default=0)
    updated_users: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_users: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
