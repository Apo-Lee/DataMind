"""系统配置模型 (V2) — key-value 管理平台运行参数"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string / int / float / bool / json
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
