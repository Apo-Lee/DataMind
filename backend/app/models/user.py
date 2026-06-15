"""用户表模型"""
# WHY: 使用 String(36) 替代 UUID 类型以兼容 PostgreSQL 和 SQLite
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    hr_director = "hr_director"
    finance_bp = "finance_bp"
    finance_director = "finance_director"
    dept_ceo = "dept_ceo"
    dept_manager = "dept_manager"
    sales_manager = "sales_manager"
    employee = "employee"
    viewer = "viewer"


class DataScope(str, enum.Enum):
    self_only = "self_only"        # 仅看到自己的数据
    team = "team"                  # 直属下级 (默认)
    dept = "dept"                  # 本部门
    dept_and_sub = "dept_and_sub"  # 本部门及子部门
    cross_dept = "cross_dept"      # 跨部门（由 extra_dept_ids 决定）
    all = "all"                    # 全公司


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # --- HR 锚点字段（V2 新增） ---
    employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    dept_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- 数据权限范围（V2 新增） ---
    data_scope: Mapped[DataScope] = mapped_column(String(20), default=DataScope.team)
    # 特殊权限：跨部门可访问的 dept_id 列表 (JSON 数组字符串)
    extra_dept_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- HR 同步元数据（V2 新增） ---
    hr_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual / hr_sync
