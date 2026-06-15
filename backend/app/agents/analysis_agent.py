"""Python 分析 Agent — 为复杂分析生成 Python 代码"""

import pandas as pd

from app.core.llm_client import llm_client
from app.core.sandbox import execute_in_sandbox

ANALYSIS_SYSTEM_PROMPT = """你是一个数据科学专家。根据用户问题和数据，生成 Python 分析代码。

要求:
1. 代码使用 pandas/numpy 分析已加载的 df DataFrame (也可用 scipy.stats)
2. 分析结果存放在以下变量:
   - result_df: DataFrame (分析后的数据表格，作为分析报告的核心表格)
   - insight: str (2-3 句核心洞察，含关键数字和业务结论)
   - charts: list[dict] (每个图表: {"type":"line|bar|pie|scatter", "title":"...", "data":{...}, "options":{...}})
3. 图表 data 格式与 ECharts 兼容:
   - line/bar: {"type":"bar", "title":"...", "xAxis":[...], "series":[{"name":"...","data":[...]}]}
   - pie: {"type":"pie", "title":"...", "data":[{"name":"...","value":...}]}
4. 统计方法参考: describe(), groupby(), corr(), value_counts(), rolling(), pct_change() 等
5. 不要 import pandas/numpy (已预导入)
6. 自主选择合适的分析方法 (趋势分析用折线, 分布用饼图, 对比用柱状图)

只输出 Python 代码，不要解释。代码块以 ```python 开头。
"""


async def analyze(question: str, df: pd.DataFrame) -> dict:
    """对数据进行深度分析"""
    data_desc = f"数据列: {list(df.columns)}\n行数: {len(df)}\n前 5 行:\n{df.head().to_string()}"
    user_msg = f"{data_desc}\n\n分析需求: {question}"

    try:
        msg = await llm_client.chat([
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        content = msg.get("content", "")
        if "```python" in content:
            code = content.split("```python", 1)[1].split("```", 1)[0].strip()
        elif "```" in content:
            code = content.split("```", 1)[1].split("```", 1)[0].strip()
        else:
            code = content.strip()

        data_json = df.to_json(orient="records", force_ascii=False)
        result = execute_in_sandbox(code, data_json)
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}
