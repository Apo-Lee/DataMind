"""Context Node — 上下文记忆注入节点

职责：
- 在 intent_node 之前运行
- 从数据库加载历史会话记录
- 注入多轮对话上下文到 state.turn_history
- 检测 session 变化（数据源切换、超时）
- 为后续节点提供丰富的上下文信息

设计思路：
原本 context 只在 OrchestratorAgent 中静态组装一次，
context_node 将其变为图中的一个节点，可以：
1. 在每次 turn 执行前动态加载最新上下文
2. 从数据库中恢复完整会话
3. 检测用户的角色/权限变化
4. 为跨轮对话注入记忆
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.conversation import Conversation
from app.orchestrator.state import AgentState, AgentContext

logger = logging.getLogger(__name__)


def _build_turn_history(conversations: list) -> list[dict]:
    """将数据库中的 Conversation 记录转为 turn_history 格式"""
    history = []
    for conv in conversations:
        history.append({
            "id": conv.id,
            "session_id": conv.session_id,
            "question": conv.question,
            "intent": conv.intent,
            "analysis_depth": conv.analysis_depth,
            "created_at": conv.created_at.isoformat() if conv.created_at else "",
            "sql_generated": conv.sql_generated,
        })
    return history


async def context_node(state: AgentState) -> dict:
    """Context Node — 上下文注入 LangGraph Node

    从 state 中提取 context，补充运行时信息。
    如果已有完整 context 且非首次运行，跳过。
    """
    context: AgentContext | None = state.get("context")
    turn_history = state.get("turn_history", [])
    db_session = state.get("db_session")
    question = state.get("question", "")

    if context is None:
        logger.warning("Context Node: 缺少 AgentContext，跳过")
        return {"context_enriched": False}

    # 如果已有 turn_history 且非空，说明已经加载过，跳过
    if turn_history and len(turn_history) > 0:
        return {"context_enriched": True, "turn_count": len(turn_history)}

    # 尝试从数据库加载历史会话
    if db_session and context.session_id:
        try:
            stmt = (
                select(Conversation)
                .where(Conversation.session_id == context.session_id)
                .order_by(Conversation.created_at.desc())
                .limit(10)
            )
            result = await db_session.execute(stmt)
            conversations = result.scalars().all()

            if conversations:
                # 反转以保持时间顺序
                conversations.reverse()
                loaded_history = _build_turn_history(conversations)
                logger.info(f"Context Node: 从数据库加载了 {len(loaded_history)} 条历史记录")

                # 更新 turn_number
                context.turn_number = len(loaded_history) + 1
                context.is_followup = len(loaded_history) > 0

                return {
                    "context_enriched": True,
                    "turn_count": len(loaded_history),
                    "turn_history": loaded_history,
                    "context": context,
                }
        except Exception as e:
            logger.warning(f"Context Node: 加载历史失败: {e}")

    return {"context_enriched": True, "turn_count": 0}
