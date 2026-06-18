# -*- coding: utf-8 -*-
"""用户问答 API — 统一到 LangGraph OrchestratorAgent（阶段2）"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.permissions import check_datasource_access
from app.database import get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.orchestrator import OrchestratorAgent
from app.orchestrator.errors import make_friendly_error, make_friendly_permission_error
from app.schemas.query import AskRequest, AskResponse, ConversationResponse

router = APIRouter(prefix="/api/query", tags=["问答"])
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """统一问答入口（委托给 LangGraph OrchestratorAgent）

    内部经过：权限校验 → 意图识别 → SQL/Tools → 分析 → 报告。
    """
    # 自动检测数据源（如果未提供 datasource_id）
    if not body.datasource_id:
        from app.orchestrator.datasource_router import detect_datasource
        ds_id, business_tag, reason = await detect_datasource(body.question, current_user, db)
        if ds_id is None:
            # ?????????????????
            user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
            if user_role == "admin":
                report_md = "**📡 没有可用的数据源**\n\n当前系统没有配置任何数据源。请前往「数据源管理」页面添加数据源后再使用。\n\n添加步骤：\n1. 点击左侧导航「数据源管理」\n2. 点击「新增数据源」\n3. 填写数据库连接信息并保存"
            elif user_role == "viewer":
                report_md = "**👀 暂无可用数据**\n\n你的账号是只读角色，目前没有分配任何数据源。请联系管理员为你分配权限。"
            else:
                report_md = "**📡 没有可用的数据源**\n\n当前没有你可以访问的数据源。请联系管理员确认：\n1. 是否已配置数据源\n2. 你的账号是否有数据源权限"
            return AskResponse(
                conversation_id="",
                intent="error",
                analysis_depth="simple",
                sql_generated="",
                insights=[],
                report_markdown=report_md,
            )
        body.datasource_id = ds_id
        logger.info(f"[ask-auto] {body.question} -> {business_tag} ({reason})")

    # 权限检查（只做数据源可见性，RLS 由 MCP server 端 contextvar 保证）
    await check_datasource_access(current_user, body.datasource_id, db)

    orchestrator = OrchestratorAgent(current_user, body.datasource_id, db)
    result = await orchestrator.run(question=body.question, deep_analyze=body.deep_analyze)

    # 映射到 AskResponse（前端只需 conversation_id + 报告字段）
    conv_id = result.get("conversation_id") or result.get("session_id", "")
    return AskResponse(
        conversation_id=str(conv_id),
        intent=result.get("intent", ""),
        analysis_depth=result.get("analysis_depth", "simple"),
        sql_generated=result.get("sql_generated", ""),
        insights=result.get("insights", []),
        report_markdown=result.get("report_markdown", ""),
    )


@router.get("/history", response_model=list[ConversationResponse])
async def list_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/history/{conv_id}", response_model=ConversationResponse)
async def get_history_detail(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv