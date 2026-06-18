"""Agent API — LangGraph 多 Agent 问答路由"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.permissions import check_datasource_access
from app.database import get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.orchestrator import OrchestratorAgent
from app.orchestrator.errors import make_friendly_query_error, make_friendly_error
from app.schemas.query import (
    AgentAskResponse, SessionCreateRequest, SessionFollowUpRequest, AutoAskRequest,
)

router = APIRouter(prefix="/api/agent", tags=["Agent 问答"])
logger = logging.getLogger(__name__)



@router.post("/ask-auto", response_model=AgentAskResponse)
async def agent_ask_auto(
    body: AutoAskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """智能问答 — 自动检测数据源

    不再需要前端传入 datasource_id，
    系统根据问题内容自动路由到最匹配的数据源。
    """
    from app.orchestrator.datasource_router import detect_datasource

    datasource_id, business_tag, reason = await detect_datasource(body.question, current_user, db)
    if datasource_id is None:
        return AgentAskResponse(
            session_id="",
            turn_id="",
            question=body.question,
            intent="error",
            analysis_depth="simple",
            sql_generated="",
            insights=[],
            report_markdown="**\U0001f605 没有可用的数据源**\n\n当前系统没有配置任何数据源，请联系管理员添加。",
            followups=[],
            conversation_history=[],
            error="no_datasource: " + reason,
        )

    logger.info(f"数据源自动检测: [{body.question}] -> {business_tag} ({reason})")

    orchestrator = OrchestratorAgent(current_user, datasource_id, db)
    result = await orchestrator.run(question=body.question)

    if result.get("error"):
        error_type = result.get("error_type", "unknown_error")
        friendly = make_friendly_error(error_type, result["error"], result.get("sql_generated", ""))
        return AgentAskResponse(
            session_id=result.get("session_id", ""),
            turn_id=result.get("turn_id", ""),
            question=body.question,
            intent="error",
            analysis_depth="simple",
            sql_generated=result.get("sql_generated", ""),
            insights=[],
            report_markdown=friendly.to_user_response()["report_markdown"],
            followups=friendly.to_user_response()["followups"],
            conversation_history=result.get("conversation_history", []),
            error=friendly.to_user_response()["error"],
        )

    return AgentAskResponse(**result)


@router.post("/ask", response_model=AgentAskResponse)
async def agent_ask(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新会话并发起一问

    LangGraph 多 Agent 编排入口。
    自动判断意图 -> SQL 查询 -> 分析 -> 报告 -> 追问建议。
    """
    # 权限检查
    await check_datasource_access(current_user, body.datasource_id, db)

    orchestrator = OrchestratorAgent(current_user, body.datasource_id, db)
    result = await orchestrator.run(question=body.question)

    if result.get("error"):
        error_type = result.get("error_type", "unknown_error")
        friendly = make_friendly_error(error_type, result["error"], result.get("sql_generated", ""))
        return AgentAskResponse(
            session_id=result.get("session_id", ""),
            turn_id=result.get("turn_id", ""),
            question=body.question,
            intent="error",
            analysis_depth="simple",
            sql_generated=result.get("sql_generated", ""),
            insights=[],
            report_markdown=friendly.to_user_response()["report_markdown"],
            followups=friendly.to_user_response()["followups"],
            conversation_history=result.get("conversation_history", []),
            error=friendly.to_user_response()["error"],
        )

    return AgentAskResponse(**result)


@router.post("/followup", response_model=AgentAskResponse)
async def agent_followup(
    body: SessionFollowUpRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """追问 — 在已有会话基础上继续对话"""
    # 获取历史对话
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(5)
    )
    history = result.scalars().all()

    # 构建历史摘要
    turn_history = [
        {
            "id": str(h.id),
            "session_id": body.session_id,
            "question": h.question,
            "intent": h.intent or "unknown",
            "analysis_depth": h.analysis_depth or "simple",
            "created_at": str(h.created_at) if h.created_at else "",
        }
        for h in history
    ]

    # 获取最后一条的 datasource_id
    datasource_id = history[0].datasource_id if history else body.session_id
    if datasource_id is None or datasource_id == body.session_id:
        # 尝试从历史找到 datasource_id
        for h in history:
            if h.datasource_id:
                datasource_id = h.datasource_id
                break

    if not datasource_id:
        raise HTTPException(status_code=400, detail="未找到原始问题的数据源，请重新发起新问题")

    # 权限检查
    await check_datasource_access(current_user, datasource_id, db)

    orchestrator = OrchestratorAgent(current_user, datasource_id, db)
    result = await orchestrator.run(
        question=body.question,
        session_id=body.session_id,
        turn_history=turn_history,
    )

    if result.get("error"):
        error_type = result.get("error_type", "unknown_error")
        friendly = make_friendly_error(error_type, result["error"], result.get("sql_generated", ""))
        return AgentAskResponse(
            session_id=result.get("session_id", ""),
            turn_id=result.get("turn_id", ""),
            question=body.question,
            intent="error",
            analysis_depth="simple",
            sql_generated=result.get("sql_generated", ""),
            insights=[],
            report_markdown=friendly.to_user_response()["report_markdown"],
            followups=friendly.to_user_response()["followups"],
            conversation_history=result.get("conversation_history", []),
            error=friendly.to_user_response()["error"],
        )

    return AgentAskResponse(**result)


@router.get("/history/{session_id}", response_model=list[dict])
async def agent_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某次会话的完整历史"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "datasource_id": c.datasource_id,
            "question": c.question,
            "intent": c.intent,
            "analysis_depth": c.analysis_depth,
            "sql_generated": c.sql_generated,
            "report_markdown": c.report_markdown,
            "created_at": str(c.created_at) if c.created_at else "",
        }
        for c in convs
    ]
