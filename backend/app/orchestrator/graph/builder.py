"""LangGraph StateGraph 编排 — DataMind AI Agent

完整的工作流图：

                         ┌──────────┐
                         │  START   │
                         └────┬─────┘
                              │
                              ▼
                     ┌────────────────┐
                     │  intent_node   │  ← Intent Router (15类)
                     └───────┬────────┘
                             │
                     ┌───────┴────────┐
                     │ route_by_intent│
                     └───┬───────┬────┘
                         │       │
            greeting/help│       │其他
                         ▼       ▼
                  ┌──────────┐ ┌──────────┐
                  │report_node│ │ sql_node │  ← SQL Agent
                  └──────────┘ └────┬─────┘
                                    │
                            ┌───────┴────────┐
                            │ route_after_sql│
                            └───┬────────┬────┘
                                │        │
                     complex意图 │        │ 其他
                                ▼        ▼
                     ┌─────────────┐ ┌──────────┐
                     │analysis_node│ │report_node│
                     └──────┬──────┘ └──────────┘
                            │
                     ┌──────┴──────┐
                     │after_analy  │
                     └──────┬──────┘
                            ▼
                     ┌──────────┐
                     │report_node│  ← 最终报告
                     └──────────┘
"""

import logging

from langgraph.graph import END, StateGraph, START

from app.orchestrator.state import AgentState, route_by_intent, route_after_sql, should_retry, route_by_quality, route_after_mcp
from app.orchestrator.nodes.intent_node import intent_node
from app.orchestrator.nodes.sql_node import sql_node
from app.orchestrator.nodes.context_node import context_node
from app.orchestrator.nodes.quality_node import quality_node
from app.orchestrator.nodes.mcp_agent_node import mcp_agent_node

from app.orchestrator.nodes.analysis_node import analysis_node
from app.orchestrator.nodes.report_node import report_node

logger = logging.getLogger(__name__)


def build_agent_graph() -> StateGraph:
    """构建 LangGraph StateGraph

    Returns:
        可编译执行的 StateGraph
    """
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("context_node", context_node)
    graph.add_node("intent_node", intent_node)
    graph.add_node("quality_node", quality_node)
    graph.add_node("mcp_agent_node", mcp_agent_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("analysis_node", analysis_node)
    graph.add_node("report_node", report_node)

    # 从 START 到 Intent
    graph.add_edge(START, "context_node")
    graph.add_edge("context_node", "intent_node")

    # Intent 路由
    graph.add_conditional_edges(
        "intent_node",
        route_by_intent,
        {
            "quality_node": "quality_node",
            "analysis_node": "quality_node",
            "report_node": "report_node",
        },
    )

    # 质量检查 -> MCP Agent 或错误报告
    graph.add_conditional_edges(
        "quality_node",
        route_by_quality,
        {
            "mcp_agent_node": "mcp_agent_node",
            "report_node": "report_node",
        },
    )

    # MCP Agent -> 分析或报告
    graph.add_conditional_edges(
        "mcp_agent_node",
        route_after_mcp,
        {
            "analysis_node": "analysis_node",
            "report_node": "report_node",
        },
    )

    # SQL 后的条件路由
    graph.add_conditional_edges(
        "sql_node",
        route_after_sql,
        {
            "analysis_node": "analysis_node",
            "report_node": "report_node",
        },
    )

    # 分析后去报告
    graph.add_edge("analysis_node", "report_node")

    # 报告节点到 END
    graph.add_edge("report_node", END)

    return graph


# 编译为可调用的图（单例）
_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_agent_graph()
        _compiled_graph = graph.compile()
        logger.info("LangGraph Agent 图已编译完成")
    return _compiled_graph
