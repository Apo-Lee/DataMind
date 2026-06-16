"""报告组装 Agent — 将分析结果组装为 Markdown 报告"""

import pandas as pd

from app.core.llm_client import llm_client


def df_to_markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    """将 DataFrame 转换为 Markdown 表格语法，供 marked 前端渲染"""
    if df.empty:
        return "*(无数据)*"
    df_display = df.head(max_rows)
    # 表头
    header = "| " + " | ".join(str(c) for c in df_display.columns) + " |"
    # 分隔线
    sep = "| " + " | ".join("---" for _ in df_display.columns) + " |"
    # 数据行
    rows: list[str] = []
    for _, row in df_display.iterrows():
        cells = []
        for v in row:
            if v is None or (isinstance(v, float) and str(v).lower() == 'nan'):
                cells.append("-")
            else:
                s = str(v)
                # 截断过长内容
                cells.append(s[:200] + "..." if len(s) > 200 else s)
        rows.append("| " + " | ".join(cells) + " |")
    return header + "\n" + sep + "\n" + "\n".join(rows)

REPORT_SYSTEM_PROMPT = """你是一个数据分析报告撰写专家。根据用户问题和分析结果，生成一份业务可读的 Markdown 报告。

报告结构:
## 📊 分析结论 *(Analysis)*
> 2-3 句核心洞察（加粗关键数字）

## 📋 关键数据 *(Key Data)*
（表格，使用 Markdown 表格语法；如果 Python 分析返回了 result_df 就渲染该表，否则用原始数据）

## 📈 分析洞察 *(Insights)*
（如果 Python 沙箱执行了深度分析，把 insight 文本整合进来；如有统计指标(均值/中位数/标准差/趋势)也列出来）

## 💡 业务建议 *(Recommendations)*
（2-3 条可操作建议，如果不适用就跳过）

规则:
- 使用中文
- 数字保留合理精度（百分数保留1位，金额保留整数）
- 表格必须使用 Markdown 语法
- 不要输出 ECharts 配置，图表在前端独自处理
- 不要输出代码块；如有代码，改用自然语言描述分析步骤
"""


_df_to_markdown_table = df_to_markdown_table


async def assemble_report(
    question: str, sql: str, df: pd.DataFrame,
    intent: dict, analysis_result: dict | None = None,
) -> str:
    """组装 Markdown 分析报告"""
    # 使用 _df_to_markdown_table 生成 marked 可渲染的 Markdown 表格
    data_summary = (
        f"数据行数: {len(df)}\n列: {list(df.columns)}\n\n"
        f"前 10 行:\n{_df_to_markdown_table(df.head(10))}"
    )

    extra = ""
    if analysis_result and analysis_result.get("status") == "success":
        data = analysis_result.get("data", {})
        if data.get("insight"):
            extra += f"\n深度分析结果:\n{data['insight']}"
        if data.get("table"):
            try:
                table_df = pd.DataFrame(data["table"])
                extra += f"\n\n分析结果表格 ({len(table_df)}行):\n{_df_to_markdown_table(table_df, 20)}"
            except Exception:
                pass

    user_msg = f"用户问题: {question}\n分析类型: {intent.get('intent', 'unknown')}\n{data_summary}{extra}"

    try:
        msg = await llm_client.chat([
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        return msg.get("content", "# 分析报告\n\n报告生成失败，请重试。")
    except Exception as e:
        logger.warning(f"assemble_report LLM failed: {e}")
        return f"# 分析报告\n\n## 查询\n{question}\n\n## 数据\n{_df_to_markdown_table(df.head(20))}"

