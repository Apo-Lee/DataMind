"""Agent 持久层模型 — 会话追踪、长期记忆、用户反馈"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.database import Base


class AgentSession(Base):
    """Agent 会话追踪 — 多轮对话的链条管理"""
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    datasource_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="SET NULL"), nullable=True
    )
    parent_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | expired
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AgentMemory(Base):
    """Agent 长期记忆 — 用户偏好/常见模式/学到的事实"""
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    datasource_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="SET NULL"), nullable=True
    )
    memory_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # "preferred_chart_type" | "common_queries" | "recent_focus" | "learned_pattern"
    memory_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    memory_type: Mapped[str] = mapped_column(String(30), default="preference")
    # preference | pattern | learned
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        # 每个用户+数据源+key 唯一
        {
            "sqlite_autoincrement": True,
        }
    )


class AgentFeedback(Base):
    """用户反馈 — Agent 回答质量评价"""
    __tablename__ = "agent_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    turn_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SchemaColumnSample(Base):
    """数据列值样本缓存 — 减少 LLM 编造枚举值"""
    __tablename__ = "schema_column_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sample_values: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    last_sampled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        {
            "sqlite_autoincrement": True,
        }
    )
