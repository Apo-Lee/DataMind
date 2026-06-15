"""问答相关 Pydantic schemas"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class AskRequest(BaseModel):
    datasource_id: str
    question: str


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
