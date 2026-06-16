"""SQL Agent Node — 使用 SQL Tools (Function Calling 模式) 执行安全查询

流程：
1. 获取 Agent 实例
2. 构建 RowLevelSecurityEngine
3. 使用 SQLToolExecutor 执行 LLM 选定的查询工具
4. 结果返回给下一个节点
"""

import logging
import time
from typing import Any

from app.agents.factory import agent_factory
from app.core.permissions import check_datasource_access
from app.core.row_level_security import RowLevelSecurityEngine
from app.core.sql_tools import SQLToolExecutor, build_query_tools
from app.orchestrator.state import (
    AgentState, AgentContext, SQLResult, IntentType,
)

logger = logging.getLogger(__name__)


async def sql_node(state: AgentState) -> dict:
    """SQL 查询节点 — LangGraph Node

    使用 Tool/Function Calling 模式：
    - 不再让 LLM 直接生成 SQL
    - LLM 输出结构化查询参数（表名、列、过滤条件等）
    - SQLToolExecutor 注入 RLS 并构建安全 SQL
    """
    context: AgentContext | None = state.get("context")
    question = state.get("question", "")
    intent_result = state.get("intent_result")
    retry_count = state.get("retry_count", 0)

    if context is None:
        return {"sql_result": SQLResult(status="error", error="缺少 Agent 上下文"), "last_error": "Missing context"}

    db = context.db_session
    if db is None:
        return {"sql_result": SQLResult(status="error", error="数据库连接不可用"), "last_error": "No db session"}

    try:
        # Step 1: 获取数据源
        from app.models.datasource import DataSource
        from sqlalchemy import select
        ds_result = await db.execute(select(DataSource).where(DataSource.id == context.datasource_id))
        ds = ds_result.scalar_one_or_none()
        if ds is None:
            return {"sql_result": SQLResult(status="error", error="数据源不存在"), "last_error": "Datasource not found"}

        agent = agent_factory.get_or_create(ds)

        # Step 2: 构建 RLS 引擎
        rls_engine = RowLevelSecurityEngine(
            user=context.user_ref,
            datasource=ds,
            db=db,
        )

        # Step 3: 创建 SQL Tool Executor
        executor = SQLToolExecutor(
            agent=agent,
            rls_engine=rls_engine,
            user_role=context.user_role,
            user_info={
                "role": context.user_role,
                "data_scope": context.user_data_scope,
                "employee_id": context.user_employee_id,
                "dept_id": context.user_dept_id,
                "dept_name": context.user_dept_name,
            },
        )

        # Step 4: 通过 LLM Function Calling 决定查询参数
        # 先获取可见的 schema
        tables = agent.list_tables()
        from app.core.query_engine import _COLUMN_SENSITIVITY
        sens = _COLUMN_SENSITIVITY.get(ds.business_tag, {})

        tables_columns = {}
        for t in tables:
            visible_cols = _get_visible_cols_for_tool(t, ds.business_tag, context.user_role)
            tables_columns[t] = visible_cols

        tools_def = build_query_tools(
            business_tag=ds.business_tag,
            tables_columns=tables_columns,
            role=context.user_role,
            data_scope=context.user_data_scope,
        )

        # 调用 LLM 选择工具和参数
        from app.core.llm_client import llm_client

        schema_context = _build_schema_context(tables_columns, ds.business_tag)
        user_msg = (
            f"【数据源】{ds.name} ({ds.business_tag})\n"
            f"【你的角色】{context.user_role}, 数据范围={context.user_data_scope}\n"
            f"【部门】{context.user_dept_name} (ID={context.user_dept_id})\n\n"
            f"{schema_context}\n\n"
            f"用户问题: {question}\n\n"
            f"请选择合适的工具查询数据。对于统计类问题，使用 aggregations 参数。"
        )

        llm_result = await llm_client.chat(
            messages=[
                {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            tools=tools_def,
        )

        # Step 5: 处理 Tool Calling 结果
        if not llm_result.get("tool_calls"):
            # LLM 直接返回文本，没有 tool calling
            content = llm_result.get("content", "")
            logger.warning(f"LLM 未选择工具，直接返回文本: {content[:100]}")

            # 降级：从文本中解析意图，做简单查询
            return {
                "sql_result": SQLResult(
                    status="error",
                    error=f"无法生成查询: {content[:200] if content else 'LLM 未返回工具调用'}",
                    error_type="IntentError",
                ),
                "last_error": "No tool call from LLM",
            }

        # 执行第一个 tool call
        tc = llm_result["tool_calls"][0]
        tool_name = tc["function"]["name"]
        tool_args_raw = tc["function"]["arguments"]
        import json
        if isinstance(tool_args_raw, str):
            try:
                tool_args = json.loads(tool_args_raw)
            except json.JSONDecodeError:
                tool_args = {}
        else:
            tool_args = tool_args_raw

        start_time = time.time()
        exec_result = await executor.execute_tool(tool_name, tool_args)
        sql_elapsed_ms = round((time.time() - start_time) * 1000)

        if exec_result.get("status") == "error":
            error_msg = exec_result.get("error", "工具执行失败")
            logger.warning(f"SQL Tool 执行失败: {error_msg}")
            return {
                "sql_result": SQLResult(
                    status="error",
                    error=error_msg,
                    error_type="QueryError",
                ),
                "last_error": error_msg,
            }

        # 成功
        data = exec_result.get("data", {})
        rows = data.get("rows", [])
        df = _rows_to_dataframe(rows)

        return {
            "sql_result": SQLResult(
                status="success",
                sql=exec_result.get("sql", ""),
                df=df,
                rows_affected=len(df),
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


def _get_visible_cols_for_tool(table_name, business_tag, role):
    from app.core.sql_tools import _filter_visible_columns_for_role
    return _filter_visible_columns_for_role(business_tag, table_name, role)


def _build_schema_context(tables_columns: dict[str, list[dict]], business_tag: str) -> str:
    """构建 Schema 描述"""
    parts = [f"【数据源: {business_tag}】可用表和列:"]
    for tname, cols in tables_columns.items():
        col_str = ", ".join(
            f"{c['name']}({'🔒' if c['sensitive'] else '✓'}{': ' + c['description'] if c.get('description') else ''})"
            for c in cols
        )
        parts.append(f"  📋 {tname}: {col_str}")
    return "\n".join(parts)


def _rows_to_dataframe(rows: list[dict]) -> Any:
    """转换行数据为 DataFrame"""
    import pandas as pd
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


_AGENT_SYSTEM_PROMPT = """你是一个企业数据分析助手。根据用户的问题，选择合适的工具来查询数据。

规则：
1. 优先使用 query_data 工具查询具体数据
2. 如果不知道表结构，先使用 list_tables 查看可用表和列
3. 对统计类问题（数量、平均、分布、排行），使用 aggregations 参数
4. 对趋势类问题，使用 filters 设置时间范围
5. 过滤条件的值使用中文实际值（如状态用"在职"/"离职"，出服用"出勤"/"请假"）
6. 日期格式使用 YYYY-MM-DD
7. 不要查询你没有权限查看的敏感列（标记为🔒的列）
8. 严格使用工具调用获取数据，不要自行编造数据
"""
