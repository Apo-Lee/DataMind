"""对话历史表模型"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

import enum


class AnalysisDepth(str, enum.Enum):
    simple = "simple"
    complex = "complex"


class KpiPreference(Base):
    __tablename__ = "kpi_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    datasource_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled_kpi_ids: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of ids


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    datasource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analysis_depth: Mapped[AnalysisDepth | None] = mapped_column(String(10), nullable=True)
    sql_generated: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
