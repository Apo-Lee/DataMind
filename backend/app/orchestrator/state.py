"""LangGraph Agent 共享状态定义

AgentState 是整个 LangGraph 图中所有节点共享的数据结构。
每个节点读取/更新其中的部分字段，流经图完成全流程。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
from langgraph.graph import MessagesState
from langgraph.managed import IsLastStep


# ============================================================
# 意图枚举 — 15 类细化分类
# ============================================================

class IntentType(str, enum.Enum):
    """Agent 意图分类体系"""
    # 直查类
    direct_query = "direct_query"
    list_query = "list_query"
    aggregation = "aggregation"

    # 分析类
    trend = "trend"
    comparison = "comparison"
    ranking = "ranking"
    distribution = "distribution"
    anomaly = "anomaly"
    root_cause = "root_cause"
    forecast = "forecast"

    # 交互类
    drill_down = "drill_down"
    refinement = "refinement"
    cross_domain = "cross_domain"

    # 元类
    greeting = "greeting"
    help = "help"
    unknown = "unknown"


# ============================================================
# 共享 Agent State（LangGraph State）
# ============================================================

@dataclass
class AgentContext:
    """Agent 共享上下文 — 跨节点传递的非敏感信息"""
    # 用户信息（已脱敏的上下文）
    user_role: str = "employee"
    user_data_scope: str = "team"
    user_dept_name: str = ""
    user_id: str = ""
    user_employee_id: int | None = None
    user_dept_id: int | None = None

    # 会话信息
    session_id: str = ""
    turn_number: int = 1
    parent_turn_id: str | None = None
    is_followup: bool = False

    # 数据源
    datasource_id: str = ""
    business_tag: str = ""

    # 数据库 session（运行时注入）
    db_session: Any = None

    # V3: 原始 User 对象引用（用于 RLS 引擎等需要完整 User 对象的场景）
    user_ref: Any = None


@dataclass
class AgentResult:
    """标准化的 Agent 节点输出"""
    status: str = "success"               # success | error | rejected
    error: str | None = None
    error_type: str | None = None          # IntentError | PermissionError | QueryError | AnalysisError
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: str | None = None


@dataclass
class IntentResult(AgentResult):
    """意图识别节点输出"""
    intent_type: IntentType = IntentType.unknown
    intent_label: str = "unknown"
    analysis_depth: str = "simple"          # simple | complex
    entities: list[str] = field(default_factory=list)
    time_range: str = "unknown"
    refined_column: str | None = None        # 追问时修正的列名


@dataclass
class SQLResult(AgentResult):
    """SQL 节点输出"""
    sql: str = ""
    df: Optional[pd.DataFrame] = None
    rows_affected: int = 0
    execution_time_ms: float = 0
    masked_columns: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult(AgentResult):
    """分析节点输出"""
    insight: str = ""
    charts: list[dict] = field(default_factory=list)
    table: list[dict] = field(default_factory=list)


@dataclass
class ReportResult(AgentResult):
    """报告节点输出"""
    report_markdown: str = ""
    insights: list[dict] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)


# ============================================================
# AgentState 定义
# ============================================================

class AgentState(MessagesState):
    """LangGraph 全图共享状态

    继承 MessagesState 以支持 LangChain 消息传递。
    路由函数使用 dict 访问方式: state["key"]
    """
    # Agent 流程控制
    is_last_step: IsLastStep = False

    # 上下文
    context: Optional[AgentContext] = None

    # 原始输入
    question: str = ""
    original_question: str = ""

    # 各节点输出
    intent_result: Optional[IntentResult] = None
    sql_result: Optional[SQLResult] = None
    analysis_result: Optional[AnalysisResult] = None
    report_result: Optional[ReportResult] = None

    # 错误处理
    last_error: str | None = None
    retry_count: int = 0
    max_retries: int = 2

    # 会话追踪
    turn_history: list[dict] = field(default_factory=list)


# ============================================================
# 路由函数
# ============================================================

def route_by_intent(state: dict) -> str:
    """根据 intent_result 路由到下一个节点"""
    intent_result = state.get("intent_result")

    if intent_result is None or intent_result.status != "success":
        return "report_node"

    intent = intent_result.intent_type

    # 问候/帮助 -> 直接报告
    if intent in (IntentType.greeting, IntentType.help):
        return "report_node"

    # 需要深度分析 -> analysis_node
    if intent in (IntentType.root_cause, IntentType.forecast, IntentType.anomaly):
        return "analysis_node"

    # 默认都走 sql_node
    return "sql_node"


def route_after_sql(state: dict) -> str:
    """SQL 执行后决定是否需要分析"""
    sql_result = state.get("sql_result")
    intent_result = state.get("intent_result")

    if sql_result is None or sql_result.status != "success":
        if intent_result and intent_result.analysis_depth == "complex":
            return "analysis_node"
        return "report_node"

    if intent_result and intent_result.analysis_depth == "complex":
        return "analysis_node"

    return "report_node"


def route_after_analysis(state: dict) -> str:
    """分析完成后去报告节点"""
    return "report_node"


def should_retry(state: dict) -> str:
    """检查是否需要重试"""
    if state.get("last_error") and state.get("retry_count", 0) < state.get("max_retries", 2):
        return "intent_node"
    return "report_node"
