"""SQL Agent Node — 安全查询执行节点

整合现有的 sql_agent.py 和 query_engine.py 的安全能力，
作为 LangGraph 中的 SQL 执行节点。
"""

import logging
import time
from typing import Any

import pandas as pd

from app.agents.factory import agent_factory
from app.agents.sql_agent import generate_sql
from app.core.permissions import check_datasource_access
from app.core.query_engine import safe_query, mask_sensitive_data
from app.core.row_level_security import RowLevelSecurityEngine
from app.orchestrator.state import (
    AgentState, AgentContext, SQLResult, IntentType,
    route_after_sql,
)

logger = logging.getLogger(__name__)


async def sql_node(state: AgentState) -> dict:
    """SQL 查询节点 — LangGraph Node

    流程：
    1. 如果 intent 是简单类型 → 使用结构化意图路径（safe_query）
    2. 如果 intent 是复杂类型 → 使用 LLM 生成 SQL + 权限校验（generate_sql）
    3. RLS 过滤注入
    4. 结果脱敏
    """
    context: AgentContext | None = state.get("context")
    question = state.get("question", "")
    intent_result = state.get("intent_result")
    retry_count = state.get("retry_count", 0)

    if context is None:
        return {"sql_result": SQLResult(status="error", error="缺少 Agent 上下文"), "last_error": "Missing context"}

    # 获取 Agent 实例
    from app.database import get_db_sync
    from app.models.datasource import DataSource
    from sqlalchemy import select

    # 由于 db_session 是从外部传入的，需要同步获取
    db = context.db_session
    if db is None:
        return {"sql_result": SQLResult(status="error", error="数据库连接不可用"), "last_error": "No db session"}

    try:
        # Step 1: 权限检查 + 获取 Agent
        ds_result = await db.execute(select(DataSource).where(DataSource.id == context.datasource_id))
        ds = ds_result.scalar_one_or_none()
        if ds is None:
            return {"sql_result": SQLResult(status="error", error="数据源不存在"), "last_error": "Datasource not found"}

        agent = agent_factory.get_or_create(ds)

        # Step 2: 注入 RLS
        from fastapi import Depends
        rls_engine = RowLevelSecurityEngine(
            user=type("User", (), {
                "id": context.user_id,
                "role": type("Role", (), {"value": context.user_role})(),
                "data_scope": type("Scope", (), {"value": context.user_data_scope})(),
                "employee_id": context.user_employee_id,
                "dept_id": context.user_dept_id,
            })(),
            datasource=ds,
            db=db,
        )
        rls_scope = await rls_engine.compute_data_scope()
        agent.set_rls_scope(rls_scope)

        # Step 3: 注入用户信息
        agent._user_role = context.user_role
        agent._user_data_scope = context.user_data_scope
        agent._user_id = context.user_id
        agent._user_employee_id = context.user_employee_id
        agent._user_dept_id = context.user_dept_id
        agent._user_dept_name = context.user_dept_name

        # Step 4: 执行查询
        user_info = {
            "role": context.user_role,
            "data_scope": context.user_data_scope,
            "employee_id": context.user_employee_id,
            "dept_id": context.user_dept_id,
        }

        start_time = time.time()

        # 使用 safe_query（结构化意图路径，更安全）
        result = await safe_query(question, agent, user_info)
        sql_elapsed_ms = round((time.time() - start_time) * 1000)

        if result.get("rejected"):
            err_msg = result.get("error", "查询被拒绝")
            logger.warning(f"SQL 查询被拒绝: {err_msg}")
            return {
                "sql_result": SQLResult(
                    status="rejected",
                    error=err_msg,
                    error_type="PermissionError",
                ),
                "last_error": err_msg,
            }

        sql = result.get("sql", "")
        df = result.get("data")

        return {
            "sql_result": SQLResult(
                status="success",
                sql=sql,
                df=df,
                rows_affected=len(df) if df is not None else 0,
                execution_time_ms=sql_elapsed_ms,
            ),
        }

    except Exception as e:
        error_msg = f"SQL 节点执行失败: {e}"
        logger.error(error_msg)
        return {
            "sql_result": SQLResult(status="error", error=error_msg, error_type="QueryError"),
            "last_error": error_msg,
        }
