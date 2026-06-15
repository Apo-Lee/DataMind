"""Report Agent Node — 报告组装 + 追问建议节点

根据 intent 类型选择报告模板，组装 Markdown 报告，
并生成有业务价值的追问建议。
"""

import logging

from app.core.reporter import assemble_report, df_to_markdown_table
from app.core.llm_client import llm_client
from app.orchestrator.errors import make_friendly_error
from app.orchestrator.state import (
    AgentState, ReportResult, IntentResult, IntentType,
)

logger = logging.getLogger(__name__)

# 报告模板策略
_REPORT_TEMPLATES = {
    IntentType.direct_query: ["summary", "table"],
    IntentType.list_query: ["summary", "table"],
    IntentType.aggregation: ["summary", "insight"],
    IntentType.trend: ["summary", "chart_trend", "insight", "recommendation"],
    IntentType.comparison: ["summary", "table", "chart_bar", "insight", "recommendation"],
    IntentType.ranking: ["summary", "table_ranked", "insight"],
    IntentType.distribution: ["summary", "chart_pie", "insight"],
    IntentType.anomaly: ["alert", "detail_table", "cause_analysis"],
    IntentType.root_cause: ["summary", "contribution_table", "recommendation"],
    IntentType.forecast: ["summary", "chart_forecast", "recommendation"],
    IntentType.drill_down: ["context", "detail_table"],
    IntentType.refinement: ["summary", "table"],
    IntentType.cross_domain: ["summary", "cross_table", "insight"],
    IntentType.greeting: ["greeting"],
    IntentType.help: ["help"],
    IntentType.unknown: ["summary", "table"],
}

FOLLOWUP_PROMPT = """你是一个数据分析助手。根据用户的问题和查询结果，生成 2-3 条有业务价值的追问建议。

规则：
1. 追问必须是具体的、可操作的问题
2. 基于已有数据中发现的模式或异常
3. 引导用户深入分析（下钻、对比、趋势）
4. 每个追问 15 字以内
5. 用中文
6. 直接输出 JSON 数组: ["追问1", "追问2", "追问3"]
"""


async def report_node(state: AgentState) -> dict:
    """报告节点 — LangGraph Node"""
    question = state.get("question", "")
    context = state.get("context")
    intent_result: IntentResult | None = state.get("intent_result")
    sql_result = state.get("sql_result")
    analysis_result = state.get("analysis_result")

    if context is None:
        context_summary = ""
    else:
        context_summary = f"角色={context.user_role}, 数据范围={context.user_data_scope}"

    # 问候语处理
    if intent_result and intent_result.intent_type == IntentType.greeting:
        return {
            "report_result": ReportResult(
                status="success",
                report_markdown="## 👋 你好！我是 DataMind AI 助手\n\n"
                                "我可以用自然语言帮你查询和分析数据。试试问我：\n\n"
                                "- 📊 **「上个月各部门的出勤率如何？」**\n"
                                "- 📈 **「近 6 个月的销售趋势」**\n"
                                "- 🔍 **「离职率最高的部门是哪个？」**\n"
                                "- 📉 **「为什么这个月的销售额下降了？」**",
                followups=["查看各部门出勤率", "分析近6个月销售趋势", "对比不同部门绩效"],
            ),
        }

    if intent_result and intent_result.intent_type == IntentType.help:
        return {
            "report_result": ReportResult(
                status="success",
                report_markdown="## 🤖 我能帮你做什么？\n\n"
                                "### 数据查询\n"
                                "- 查询具体数值：**「上月销售额多少」**\n"
                                "- 汇总统计：**「各部门平均薪资」**\n"
                                "- 排行分析：**「销售额 Top 10 的员工」**\n\n"
                                "### 深度分析\n"
                                "- 趋势分析：**「近 6 个月出勤率变化」**\n"
                                "- 对比分析：**「A 部门和 B 部门的离职率对比」**\n"
                                "- 异常检测：**「哪些数据异常」**\n\n"
                                "### 跨域分析\n"
                                "- **「对比 HR 和 CRM 数据」**",
                followups=["查看各部门出勤率", "分析近6个月销售趋势"],
            ),
        }

    # 构建数据摘要
    df = sql_result.df if sql_result else None
    sql = sql_result.sql if sql_result else ""
    analysis_data = analysis_result.dict() if analysis_result and analysis_result.status == "success" else None

    # 生成报告
    try:
        if intent_result and intent_result.analysis_depth == "complex":
            analysis_for_report = {
                "status": analysis_result.status if analysis_result else "error",
                "data": {
                    "insight": analysis_result.insight if analysis_result else "",
                    "charts": analysis_result.charts if analysis_result else [],
                    "table": analysis_result.table if analysis_result else [],
                }
            } if analysis_result else None

            report_md = await assemble_report(
                question=question,
                sql=sql,
                df=df,
                intent={"intent": intent_result.intent_label, "analysis_depth": intent_result.analysis_depth},
                analysis_result=analysis_for_report,
            )
        else:
            report_md = _build_simple_report(question, sql, df)
    except Exception as e:
        logger.warning(f"报告生成失败: {e}")
        report_md = _build_simple_report(question, sql, df)

    # 组装 insights
    insights = []
    if analysis_result and analysis_result.status == "success":
        if analysis_result.insight:
            insights.append({"type": "text", "content": analysis_result.insight})
        for chart in analysis_result.charts:
            insights.append({"type": "chart", "content": chart})
    elif df is not None and not df.empty:
        insights.append({"type": "table", "content": df.head(50).to_dict(orient="records")})

    # 生成追问建议
    followups = await _generate_followups(question, df, intent_result)

    return {
        "report_result": ReportResult(
            status="success",
            report_markdown=report_md,
            insights=insights,
            followups=followups,
        ),
    }


def _build_simple_report(question: str, sql: str, df) -> str:
    """简单的报告构建（当 LLM 报告失败时的回退）"""
    md = "## 查询结果\n\n"
    if sql:
        md += "> 基于以下 SQL 查询:\n\n```sql\n" + sql + "\n```\n\n"
    if df is None or df.empty:
        md += "**查询完成，未找到匹配的记录**\n\n"
        md += "建议: 检查查询条件中的时间范围或筛选条件是否正确。\n"
    else:
        md += "共查询到 **" + str(len(df)) + "** 条记录\n\n"
        md += df_to_markdown_table(df, max_rows=50)
    return md


async def _generate_followups(question: str, df, intent_result: IntentResult | None) -> list[str]:
    """生成追问建议"""
    rules: list[str] = []

    if df is not None and not df.empty:
        num_cols = list(df.select_dtypes(include=["number"]).columns)
        cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)

        # 规则1：有时间列但没做趋势
        time_keywords = ["date", "time", "month", "year", "day", "日期", "时间", "月", "年"]
        has_time = any(any(kw in str(c).lower() for kw in time_keywords) for c in df.columns)
        if has_time and intent_result and intent_result.intent_type != IntentType.trend:
            rules.append("查看变化趋势如何？")

        # 规则2：有分类列可对比
        if len(cat_cols) >= 2 and intent_result and intent_result.intent_type != IntentType.comparison:
            rules.append(f"按{cat_cols[0]}对比分析？")

        # 规则3：有数值列可排行
        if num_cols and intent_result and intent_result.intent_type != IntentType.ranking:
            rules.append(f"{num_cols[0]} Top 10 是哪些？")

        # 规则4：有异常值可检测
        if num_cols:
            for col in num_cols[:2]:
                q75, q25 = df[col].quantile(0.75), df[col].quantile(0.25)
                iqr = q75 - q25
                if iqr > 0:
                    outliers = df[(df[col] < q25 - 1.5*iqr) | (df[col] > q75 + 1.5*iqr)]
                    if len(outliers) > 0 and intent_result and intent_result.intent_type != IntentType.anomaly:
                        rules.append(f"发现{len(outliers)}个异常值，需要分析原因？")
                        break

    # LLM 补充 1-2 条
    try:
        llm_followups = await llm_client.chat([
            {"role": "system", "content": FOLLOWUP_PROMPT},
            {"role": "user", "content": f"用户问题: {question}\n数据: {len(df)}行, {list(df.columns) if df is not None else '空'}"},
        ])
        import json
        content = llm_followups.get("content", "[]")
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        llm_rules = json.loads(content)
        if isinstance(llm_rules, list):
            rules.extend(llm_rules[:2])
    except Exception:
        pass

    return rules[:4]  # 最多 4 条
