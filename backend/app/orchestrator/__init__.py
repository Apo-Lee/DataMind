"""Orchestrator Agent — DataMind 多 Agent 编排主入口

Orchestrator 是用户和 LangGraph 之间的桥梁：
1. 初始化 AgentContext
2. 管理会话状态（多轮对话记忆）
3. 调用 LangGraph 图执行
4. 组装最终响应
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_agent_with_rls
from app.models.user import User
from app.models.conversation import Conversation
from app.orchestrator.state import (
    AgentState, AgentContext, IntentResult, SQLResult, AnalysisResult, ReportResult,
)
from app.orchestrator.graph.builder import get_compiled_graph
from app.orchestrator.errors import (
    AgentFriendlyError, AgentErrorType,
    make_friendly_error, make_friendly_intent_error, make_friendly_permission_error,
    make_friendly_query_error,
)


logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator Agent — 多 Agent 编排主控器

    职责：
    - 管理用户会话
    - 组装 AgentState
    - 调用 LangGraph 图
    - 持久化会话记录
    - 组装最终响应
    """

    def __init__(self, user: User, datasource_id: str, db: AsyncSession):
        self.user = user
        self.datasource_id = datasource_id
        self.db = db
        self.session_id = None

    async def run(
        self,
        question: str,
        session_id: str | None = None,
        turn_history: list[dict] | None = None,
    ) -> dict:
        """执行一个完整的 Agent 问答流程

        Args:
            question: 用户问题
            session_id: 会话ID（追问时传入）
            turn_history: 历史对话摘要（追问时传入）

        Returns:
            dict: {
                "session_id": str,
                "turn_id": str,
                "question": str,
                "intent": str,
                "analysis_depth": str,
                "sql_generated": str,
                "insights": list[dict],
                "report_markdown": str,
                "followups": list[str],
                "conversation_history": list[dict],
                "error": str | None,
            }
        """
        turn_id = str(uuid.uuid4())
        self.session_id = session_id or turn_id

        # 获取业务标签
        from app.models.datasource import DataSource
        ds_result = await self.db.execute(
            select(DataSource).where(DataSource.id == self.datasource_id)
        )
        ds = ds_result.scalar_one_or_none()
        business_tag = ds.business_tag if ds else ""

        # 构建 AgentContext
        context = AgentContext(
            user_role=self.user.role.value if hasattr(self.user.role, "value") else str(self.user.role),
            user_data_scope=self.user.data_scope.value if hasattr(self.user.data_scope, "value") else str(self.user.data_scope),
            user_dept_name=str(getattr(self.user, "dept_name", "")),
            user_id=self.user.id,
            user_employee_id=self.user.employee_id,
            user_dept_id=self.user.dept_id,
            session_id=self.session_id,
            turn_number=(turn_history or []).__len__() + 1,
            parent_turn_id=None,
            is_followup=bool(session_id and turn_history),
            datasource_id=self.datasource_id,
            business_tag=business_tag,
            db_session=self.db,
        )

        # 构建 AgentState
        initial_state: AgentState = {
            "question": question,
            "original_question": question,
            "context": context,
            "turn_history": turn_history or [],
            "intent_result": None,
            "sql_result": None,
            "analysis_result": None,
            "report_result": None,
            "last_error": None,
            "retry_count": 0,
            "messages": [],
        }

        try:
            # 编译和调用 LangGraph
            graph = get_compiled_graph()
            result = await graph.ainvoke(initial_state)

            # 提取结果
            report_result: ReportResult | None = result.get("report_result")
            intent_result: IntentResult | None = result.get("intent_result")
            sql_result: SQLResult | None = result.get("sql_result")

            # 组装响应
            response = self._build_response(
                question=question,
                turn_id=turn_id,
                session_id=self.session_id,
                intent_result=intent_result,
                sql_result=sql_result,
                report_result=report_result,
                turn_history=turn_history,
            )

            # 持久化到 Conversation 表（保持向后兼容）
            await self._persist_conversation(question, intent_result, sql_result, report_result)

            return response

        except Exception as e:
            logger.error(f"Agent \xe6\x89\xa7\xe8\xa1\x8c\xe5\xa4\xb1\xe8\xb4\xa5: {e}", exc_info=True)
            if isinstance(e, AgentFriendlyError):
                friendly = e
            else:
                friendly = make_friendly_error("unknown", str(e))
            friendly_resp = friendly.to_user_response()
            return {
                "session_id": self.session_id,
                "turn_id": turn_id,
                "question": question,
                "intent": "error",
                "analysis_depth": "simple",
                "sql_generated": "",
                "insights": [],
                "report_markdown": friendly_resp["report_markdown"],
                "followups": friendly_resp["followups"],
                "conversation_history": turn_history or [],
                "error": friendly_resp["error"],
                "error_type": friendly_resp["error_type"],
            }

    def _build_response(self, question, turn_id, session_id,
                        intent_result, sql_result, report_result, turn_history):
        """组装 Agent 响应"""
        if report_result and report_result.status == "success":
            intent_type = intent_result.intent_type.value if intent_result else "unknown"
            depth = intent_result.analysis_depth if intent_result else "simple"

            # 更新历史记录
            history_entry = {
                "id": turn_id,
                "session_id": session_id,
                "question": question,
                "intent": intent_type,
                "analysis_depth": depth,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            history = (turn_history or []) + [history_entry]

            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "question": question,
                "intent": intent_type,
                "analysis_depth": depth,
                "sql_generated": sql_result.sql if sql_result else "",
                "insights": report_result.insights,
                "report_markdown": report_result.report_markdown,
                "followups": report_result.followups,
                "conversation_history": history,
                "error": None,
            }
        # error handling with friendly messages
        error_msg = "处理失败"
        if report_result:
            error_msg = report_result.error or error_msg
        elif sql_result:
            error_msg = sql_result.error or error_msg

        # use friendly error if available
        if report_result and getattr(report_result, "error_type", None):
            sql_str = getattr(sql_result, "sql", "") if sql_result else ""
            friendly = make_friendly_error(
                report_result.error_type,
                error_msg,
                sql_str,
            )
            friendly_resp = friendly.to_user_response()
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "question": question,
                "intent": "error",
                "analysis_depth": "simple",
                "sql_generated": sql_result.sql if sql_result else "",
                "insights": [],
                "report_markdown": friendly_resp["report_markdown"],
                "followups": friendly_resp["followups"],
                "conversation_history": turn_history or [],
                "error": friendly_resp["error"],
                "error_type": friendly_resp["error_type"],
            }

        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "question": question,
            "intent": "error",
            "analysis_depth": "simple",
            "sql_generated": sql_result.sql if sql_result else "",
            "insights": [],
            "report_markdown": f"## {error_msg}",
            "followups": [],
            "conversation_history": turn_history or [],
            "error": error_msg,
        }

    async def _persist_conversation(self, question, intent_result, sql_result, report_result):
        """持久化到 Conversation 表"""
        try:
            intent_type_str = intent_result.intent_type.value if intent_result else "unknown"
            depth_str = intent_result.analysis_depth if intent_result else "simple"
            sql = sql_result.sql if sql_result else ""
            insights = report_result.insights if report_result else []
            report_md = report_result.report_markdown if report_result else ""

            conv = Conversation(
                user_id=self.user.id,
                datasource_id=self.datasource_id,
                question=question,
                intent=intent_type_str,
                analysis_depth=depth_str,
                sql_generated=sql,
                result_data={"insights": insights},
                report_markdown=report_md,
            )
            self.db.add(conv)
            await self.db.commit()
        except Exception as e:
            logger.warning(f"持久化 Conversation 失败: {e}")
            await self.db.rollback()
