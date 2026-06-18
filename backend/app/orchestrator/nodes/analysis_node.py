"""Analysis Agent Node --- LLM-driven data analysis and visualization"""
import json, logging
import pandas as pd

from app.core.llm_client import llm_client
from app.orchestrator.state import (
    AgentState, AnalysisResult,
)

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are a data analyst. Given SQL query results, generate analysis and ECharts-compatible charts.

Return ONLY a JSON object (no markdown, no explanation):
{
    "insight": "2-3 sentences of key findings in Chinese, with actual numbers",
    "charts": [
        {
            "type": "bar|line|pie|scatter|horizontal_bar",
            "title": "Chart title in Chinese",
            "series_name": "Series name",
            "x_data": ["cat1", "cat2", ...],
            "series_data": [val1, val2, ...]
        }
    ]
}

Rules:
- insight must include actual numbers from the data
- For category+value data use bar chart
- For time series use line chart
- For distribution/percentage use pie chart
- For correlation between two numeric columns use scatter
- For ranking with long labels use horizontal_bar
- Max 3 charts, each chart must have meaningful data
- x_data and series_data must be same length
"""


async def analysis_node(state: AgentState) -> dict:
    """分析节点 — 根据 SQL 查询结果生成分析报告和 ECharts 可视化"""
    mcp_result = state.get("mcp_result")
    question = state.get("question", "")
    result = mcp_result or state.get("sql_result")

    if result is None or result.df is None or result.df.empty:
        return {"analysis_result": AnalysisResult(status="success", insight="没有查询到数据，无法进行分析。")}

    df = result.df

    # 构建数据摘要
    buf = []
    buf.append("DataFrame: " + str(len(df)) + " rows x " + str(len(df.columns)) + " columns")
    buf.append("Columns: " + str(list(df.columns)))

    num_cols = list(df.select_dtypes(include=["number"]).columns)
    cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)

    if num_cols:
        buf.append("Numeric columns: " + str(num_cols))
        desc = df[num_cols].describe().to_dict()
        buf.append("Numeric stats: " + str(desc))

    if cat_cols:
        for col in cat_cols[:5]:
            vc = df[col].value_counts().head(8).to_dict()
            buf.append(str(col) + " top values: " + str(vc))

    # 添加前 10 行样例数据
    buf.append("Sample data (first 10 rows):")
    buf.append(str(df.head(10).to_dict(orient="records")))

    prompt = ANALYSIS_PROMPT + "\n\nQuestion: " + question + "\n\nData:\n" + "\n".join(buf)

    try:
        msg = await llm_client.chat([{"role": "system", "content": prompt}])
        content = msg.get("content", "").strip()

        # 处理可能的 markdown 代码块包裹
        if content.startswith("```"):
            lines = content.split("\n", 1)
            if len(lines) > 1:
                content = lines[1]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].strip()

        parsed = json.loads(content)
        insight_text = parsed.get("insight", "")
        raw_charts = parsed.get("charts", [])

        # 将 LLM 原始图表配置转换为 ECharts option
        charts = _build_echarts_options(raw_charts)

        logger.info("Analysis complete: %d chart(s) generated", len(charts))
        return {"analysis_result": AnalysisResult(status="success", insight=insight_text, charts=charts)}

    except Exception as e:
        logger.warning("LLM analysis failed, using fallback: %s", e)
        return _fallback_analysis(df, question)


def _build_echarts_options(raw_charts: list[dict]) -> list[dict]:
    """将 LLM 输出的原始图表定义转换为标准的 ECharts option 字典"""
    charts = []
    for ch in raw_charts:
        try:
            ctype = ch.get("type", "bar")
            title = ch.get("title", "")
            x_data = ch.get("x_data", [])
            s_data = ch.get("series_data", [])
            series_name = ch.get("series_name", title)

            if not x_data or not s_data:
                continue

            # 确保 x_data 和 s_data 长度一致
            min_len = min(len(x_data), len(s_data))
            x_data = x_data[:min_len]
            s_data = s_data[:min_len]

            opt = {
                "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            }

            if ctype == "pie":
                opt["tooltip"] = {"trigger": "item", "formatter": "{b}: {c} ({d}%)"}
                pie_data = [{"name": str(x_data[i]), "value": s_data[i]} for i in range(min_len)]
                opt["series"] = [{
                    "type": "pie",
                    "radius": ["35%", "60%"],
                    "data": pie_data,
                    "label": {"show": True, "formatter": "{b}: {d}%"},
                }]
                opt.pop("grid", None)

            elif ctype == "line":
                opt["xAxis"] = {"type": "category", "data": x_data, "axisLabel": {"rotate": 30 if min_len > 8 else 0}}
                opt["yAxis"] = {"type": "value"}
                opt["series"] = [{"type": "line", "name": series_name, "data": s_data, "smooth": True, "symbol": "circle", "symbolSize": 6}]

            elif ctype == "scatter":
                opt["tooltip"] = {"trigger": "item", "formatter": "{a}: ({c})"}
                opt["xAxis"] = {"type": "category", "data": x_data, "axisLabel": {"rotate": 30 if min_len > 8 else 0}}
                opt["yAxis"] = {"type": "value"}
                opt["series"] = [{"type": "scatter", "name": series_name, "data": s_data, "symbolSize": 10}]

            elif ctype == "horizontal_bar":
                opt["tooltip"] = {"trigger": "axis", "axisPointer": {"type": "shadow"}}
                opt["xAxis"] = {"type": "value"}
                opt["yAxis"] = {"type": "category", "data": x_data}
                opt["series"] = [{"type": "bar", "name": series_name, "data": s_data}]

            else:  # bar (default)
                opt["xAxis"] = {"type": "category", "data": x_data, "axisLabel": {"rotate": 30 if min_len > 8 else 0}}
                opt["yAxis"] = {"type": "value"}
                opt["series"] = [{"type": "bar", "name": series_name, "data": s_data}]

            charts.append(opt)

        except Exception as e:
            logger.warning("Skipping chart due to error: %s", e)
            continue

    return charts


def _fallback_analysis(df: pd.DataFrame, question: str) -> dict:
    """当 LLM 分析失败时的备用分析逻辑"""
    num_cols = list(df.select_dtypes(include=["number"]).columns)
    cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)

    parts = []
    charts = []

    # 数值列统计分析
    if num_cols:
        s = df[num_cols].describe()
        for col in num_cols[:3]:
            parts.append(str(col) + ": 均值=" + str(round(s[col]["mean"], 1)) + ", 最大值=" + str(round(s[col]["max"], 1)) + ", 最小值=" + str(round(s[col]["min"], 1)))

    # 分类列频次统计
    if cat_cols:
        for col in cat_cols[:3]:
            t = df[col].value_counts().head(1)
            if not t.empty:
                parts.append("Top " + str(col) + ": " + str(t.index[0]) + " (计数=" + str(t.values[0]) + ")")

    # 生成柱状图（分类 + 数值组合最优时）
    if num_cols and cat_cols:
        group_col = cat_cols[0]
        value_col = num_cols[0]
        grouped = df.groupby(group_col)[value_col].sum().sort_values(ascending=False).head(10)
        opt = {
            "title": {"text": str(group_col) + " 按 " + str(value_col), "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": [str(x) for x in grouped.index], "axisLabel": {"rotate": 30}},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": [round(float(v), 2) for v in grouped.values]}],
        }
        charts.append(opt)

    # 如果有多个数值列，生成对比图
    if len(num_cols) >= 2 and cat_cols:
        group_col = cat_cols[0]
        grouped = df.groupby(group_col)[num_cols[:2]].sum().head(10)
        opt = {
            "title": {"text": "多指标对比", "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": [str(x) for x in grouped.index], "axisLabel": {"rotate": 30}},
            "yAxis": {"type": "value"},
            "series": [
                {"type": "bar", "name": str(num_cols[0]), "data": [round(float(v), 2) for v in grouped[num_cols[0]].values]},
                {"type": "bar", "name": str(num_cols[1]), "data": [round(float(v), 2) for v in grouped[num_cols[1]].values]},
            ],
        }
        charts.append(opt)

    insight_text = "; ".join(parts) if parts else "完成数据分析。"
    return {"analysis_result": AnalysisResult(status="success", insight=insight_text, charts=charts)}
