"""Analysis Agent Node — 深度分析节点

对 SQL 查询结果进行 Python 深度分析（趋势、对比、异常检测、预测），
在 Docker 沙箱中安全执行 LLM 生成的代码。
"""

import json
import logging

import pandas as pd

from app.agents.analysis_agent import analyze as analysis_agent_analyze
from app.core.sandbox import execute_in_sandbox
from app.orchestrator.state import (
    AgentState, AnalysisResult, IntentType,
)

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT_V2 = """你是一个数据科学专家。根据用户问题、意图类型和数据，生成 Python 分析代码。

意图类型说明:
- trend: 时间趋势分析 — 使用折线图展示变化，计算环比/同比
- comparison: 对比分析 — 分组对比，使用柱状图
- ranking: 排行分析 — Top N 排行
- distribution: 分布分析 — 使用饼图/直方图
- anomaly: 异常检测 — 统计方法识别异常值
- root_cause: 根因分析 — 贡献度拆解，使用瀑布图/堆叠图
- forecast: 预测 — 简单线性回归/移动平均预测

要求:
1. 代码使用 pandas/numpy 分析已加载的 df DataFrame (也可用 scipy.stats)
2. 分析结果存放在以下变量:
   - result_df: DataFrame (分析后的数据表格)
   - insight: str (2-3 句核心洞察，含关键数字和业务结论)
   - charts: list[dict] (每个图表: {"type":"line|bar|pie|scatter", "title":"...", "data":{...}, "options":{...}})
3. 图表 data 格式与 ECharts 兼容:
   - line/bar: {"type":"line", "title":"...", "xAxis":[...], "series":[{"name":"...","data":[...]}]}
   - pie: {"type":"pie", "title":"...", "data":[{"name":"...","value":...}]}
4. 不要 import pandas/numpy (已预导入)
5. 只输出 Python 代码，不要解释。代码块以 ```python 开头。

统计方法参考: describe(), groupby(), corr(), value_counts(), rolling(), pct_change(), diff(), cumsum()
"""


async def analysis_node(state: AgentState) -> dict:
    """分析节点 — LangGraph Node"""
    question = state.get("question", "")
    intent_result = state.get("intent_result")
    sql_result = state.get("sql_result")

    if sql_result is None or sql_result.df is None or sql_result.df.empty:
        return {
            "analysis_result": AnalysisResult(
                status="success",
                insight="数据为空，无需深度分析",
            ),
        }

    df = sql_result.df
    intent_type = intent_result.intent_type if intent_result else IntentType.unknown

    try:
        # 尝试使用现有的 analyze 函数
        analysis_result = await analysis_agent_analyze(question, df)

        if analysis_result and analysis_result.get("status") == "success":
            data = analysis_result.get("data", {})
            return {
                "analysis_result": AnalysisResult(
                    status="success",
                    insight=data.get("insight", ""),
                    charts=data.get("charts", []),
                    table=data.get("table", []),
                ),
            }

        # 如果失败，回退到简单的统计分析
        logger.warning(f"深度分析失败: {analysis_result.get('error', '')}")
        return _fallback_analysis(df, intent_type)

    except Exception as e:
        logger.warning(f"分析节点异常: {e}")
        return _fallback_analysis(df, intent_type)


def _fallback_analysis(df: pd.DataFrame, intent_type: IntentType) -> dict:
    """回退分析：当 LLM 分析失败时使用的基于规则的统计"""
    num_cols = list(df.select_dtypes(include=["number"]).columns)
    cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)

    insight_parts = []

    # 基本统计
    if num_cols:
        stats = df[num_cols].describe()
        for col in num_cols[:3]:
            insight_parts.append(
                f"{col}: 均值={stats[col]['mean']:.1f}, "
                f"最大={stats[col]['max']:.1f}, 最小={stats[col]['min']:.1f}"
            )

    # 分类统计
    if cat_cols:
        for col in cat_cols[:2]:
            top_val = df[col].value_counts().head(1)
            if not top_val.empty:
                insight_parts.append(f"{col}中最多的是'{top_val.index[0]}'，共{top_val.values[0]}条")

    charts = []
    # 如果有数值列和分类列，生成柱状图
    if num_cols and cat_cols:
        top_cats = df.groupby(cat_cols[0])[num_cols[0]].sum().sort_values(ascending=False).head(10)
        charts.append({
            "type": "bar",
            "title": f"各{cat_cols[0]}{num_cols[0]}分布(Top 10)",
            "data": {
                "xAxis": [str(x) for x in top_cats.index],
                "series": [{"name": num_cols[0], "data": [round(v, 2) for v in top_cats.values]}],
            },
        })

    return {
        "analysis_result": AnalysisResult(
            status="success",
            insight="；".join(insight_parts) if insight_parts else "已完成统计分析",
            charts=charts,
        ),
    }
