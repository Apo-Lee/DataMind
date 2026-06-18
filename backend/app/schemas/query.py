"""问答相关 Pydantic schemas"""

from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


class AskRequest(BaseModel):
    datasource_id: str = ""
    question: str
    deep_analyze: bool = False


class AskResponse(BaseModel):
    conversation_id: str
    intent: str
    analysis_depth: str
    sql_generated: str
    insights: list[dict] = []
    report_markdown: str = ""


class ConversationResponse(BaseModel):
    id: str
    question: str
    intent: str | None = None
    analysis_depth: str | None = None
    report_markdown: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


# ============================================================
# LangGraph Agent Schemas（新增）
# ============================================================

class AgentTurn(BaseModel):
    """单轮 Agent 对话记录"""
    id: str
    session_id: str
    question: str
    intent: str = "unknown"
    analysis_depth: str = "simple"
    sql_generated: str = ""
    result_data: dict | None = None
    report_markdown: str = ""
    insights: list[dict] = []
    followups: list[str] = []
    error: str | None = None
    created_at: str = ""

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class SessionCreateRequest(BaseModel):
    """创建新会话请求"""
    datasource_id: str
    question: str


class SessionFollowUpRequest(BaseModel):
    """追问请求"""
    session_id: str
    question: str


class AgentAskResponse(BaseModel):
    """Agent 统一响应"""
    session_id: str
    turn_id: str
    question: str
    intent: str
    analysis_depth: str
    sql_generated: str
    insights: list[dict] = []
    report_markdown: str = ""
    followups: list[str] = []
    conversation_history: list[dict] = []
    error: str | None = None
class AutoAskRequest(BaseModel):
    """自动检测数据源问答请求"""
    question: str

