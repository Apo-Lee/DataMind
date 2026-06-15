"""行级安全策略 & 增强的数据源权限模型 (V2)"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RowLevelPolicy(Base):
    """行级安全策略 (RLS) — 定义某数据源某表的行过滤规则"""
    __tablename__ = "row_level_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 策略类型: "dept_filter"(部门过滤), "employee_filter"(员工过滤), "custom_sql"(自定义SQL)
    policy_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # 列配置(JSON):
    # dept_filter:  {"column": "dept_id", "hierarchy": true}
    # employee_filter: {"column": "owner_id", "manager_column": "manager_id"}
    # custom_sql: {"where_clause": "dept_id IN ({allowed_depts})"}
    policy_config: Mapped[dict] = mapped_column(JSON, nullable=False)

    # 表级别（NULL=全部表）
    target_table: Mapped[str | None] = mapped_column(String(100), nullable=True)

    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
