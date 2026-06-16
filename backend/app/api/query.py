# -*- coding: utf-8 -*-
"""用户问答 API — 零风险查询引擎"""

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.agents.factory import agent_factory
from app.agents.intent import detect_intent
from app.agents.sql_agent import generate_sql
from app.core.query_engine import safe_query
from app.agents.analysis_agent import analyze
from app.core.audit import write_audit_log
from app.core.auth import get_current_user, get_role_str
from app.core.reporter import assemble_report, df_to_markdown_table
from app.core.row_level_security import RowLevelSecurityEngine
from app.core.permissions import get_agent_with_rls
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.conversation import AnalysisDepth, Conversation
from app.models.datasource import DataSource, DataSourcePermission
from app.models.user import User, UserRole
from app.schemas.query import AskRequest, AskResponse, ConversationResponse
from app.core.llm_client import llm_client
from app.orchestrator.errors import make_friendly_permission_error, make_friendly_error

_SIMPLE_SUMMARY_PROMPT = """你是一个数据分析助手。根据用户的查询问题和 SQL 查询结果，用中文给出简短的分析总结。

要求：
1. 用 2-3 句话提炼数据中的关键信息和业务洞察
2. 突出关键数字（总数、平均值、最大值、最小值等）
3. 不编造数据，严格基于提供的数据表
4. 用口语化的中文，不要用 Markdown 格式
5. 如果数据为空，说明可能的原因
"""


def _build_simple_summary(question, sql, df):
    rows = len(df)
    cols = list(df.columns) if not df.empty else []
    if df.empty:
        return "查询完成，未找到匹配的记录"
    parts = []
    parts.append("问题: " + question)
    parts.append("查询SQL: " + sql)
    parts.append("结果共 " + str(rows) + " 行，列: " + str(cols))
    if rows > 0:
        parts.append("数据样本（前" + str(min(rows, 10)) + "行）:")
        parts.append(df.head(10).to_string())
        num_cols = list(df.select_dtypes(include=["number"]).columns)
        if num_cols:
            parts.append("数值列统计:")
            parts.append(df[num_cols].describe().to_string())
    return chr(10).join(parts)


router = APIRouter(prefix="/api/query", tags=["问答"])
logger = logging.getLogger(__name__)


def _build_simple_report(question, sql, df):
    rows = len(df)
    md = "## 查询结果\n\n"
    md += "> 基于以下 SQL 查询:\n\n"
    md += "```sql\n" + sql + "\n```\n\n"
    if df.empty:
        md += "**查询完成，未找到匹配的记录**\n\n"
        md += "建议: 检查查询条件中的时间范围或筛选条件是否正确。\n"
    else:
        md += "共查询到 **" + str(rows) + "** 条记录\n\n"
        md += df_to_markdown_table(df, max_rows=50)
    return md


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """零风险查询引擎：结构化意图 -> 权限校验 -> 受控SQL -> 脱敏"""
    agent, ds = await get_agent_with_rls(current_user, body.datasource_id, db)
    agent._user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    agent._user_data_scope = current_user.data_scope.value if hasattr(current_user.data_scope, "value") else current_user.data_scope
    agent._user_id = current_user.id
    agent._user_employee_id = current_user.employee_id
    agent._user_dept_id = current_user.dept_id
    agent._user_dept_name = str(getattr(current_user, "dept_name", ""))

    user_info = {
        "role": agent._user_role,
        "data_scope": agent._user_data_scope,
        "employee_id": agent._user_employee_id,
        "dept_id": agent._user_dept_id,
    }
    intent = await detect_intent(body.question, ds.schema_summary)

    start_time = time.time()
    result = await safe_query(body.question, agent, user_info)
    sql_elapsed_ms = round((time.time() - start_time) * 1000)

    if result.get("rejected"):
        error = result.get("error", "查询被拒绝")
        friendly = make_friendly_permission_error(error)
        return AskResponse(
            conversation_id="",
            intent="rejected",
            analysis_depth="simple",
            sql_generated="",
            insights=[],
            report_markdown=friendly.to_user_response()["report_markdown"],
        )
    
    sql = result.get("sql", "")
    df = result.get("data", None)
    analysis_depth = intent.get("analysis_depth", "simple")
    insights = []
    analysis_result = None

    if analysis_depth == "complex":
        analysis_result = await analyze(body.question, df)
        if analysis_result and analysis_result.get("status") == "success":
            data = analysis_result.get("data", {})
            if data.get("insight"):
                insights.append({"type": "text", "content": data["insight"]})
            if data.get("charts"):
                for ch in data["charts"]:
                    insights.append({"type": "chart", "content": ch})
            if data.get("table"):
                insights.append({"type": "table", "content": data["table"]})
        report_md = await assemble_report(
            question=body.question, sql=sql, df=df,
            intent=intent, analysis_result=analysis_result,
        )
    else:
        if df is not None and not df.empty:
            insights.append({"type": "table", "content": df.head(50).to_dict(orient="records")})
            try:
                analysis_for_report = {
                    "status": analysis_result.get("status") if analysis_result else "success",
                    "data": {
                        "insight": analysis_result.get("data", {}).get("insight", "") if analysis_result and analysis_result.get("status") == "success" else "",
                        "table": analysis_result.get("data", {}).get("table", []) if analysis_result and analysis_result.get("status") == "success" else [],
                    }
                } if analysis_result else None
                report_md = await assemble_report(
                    question=body.question,
                    sql=sql,
                    df=df,
                    intent=intent,
                    analysis_result=analysis_for_report,
                )
            except Exception:
                pass
        if not report_md:
            report_md = _build_simple_report(body.question, sql, df)

    if df is not None and not df.empty and not insights:
        insights.append({"type": "table", "content": df.head(50).to_dict(orient="records")})

    depth_str = intent.get("analysis_depth", "simple")
    if depth_str not in AnalysisDepth.__members__:
        depth_str = AnalysisDepth.simple.value

    conv = Conversation(
        user_id=current_user.id, datasource_id=body.datasource_id,
        question=body.question, intent=intent.get("intent"),
        analysis_depth=AnalysisDepth(depth_str),
        sql_generated=sql,
        result_data={"insights": insights, "query_time_ms": sql_elapsed_ms},
        report_markdown=report_md,
    )
    db.add(conv)
    await write_audit_log(
        db, current_user, AuditAction.query_executed,
        resource_type="datasource", resource_id=body.datasource_id,
        detail={
            "question": body.question[:200],
            "intent": intent.get("intent"),
            "rows": len(df) if df is not None else 0,
        },
    )
    await db.commit()
    await db.refresh(conv)
    return AskResponse(
        conversation_id=conv.id,
        intent=intent.get("intent", "unknown"),
        analysis_depth=analysis_depth,
        sql_generated=sql,
        insights=insights,
        report_markdown=report_md,
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
