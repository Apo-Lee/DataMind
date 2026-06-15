"""意图识别 Agent — 分析用户问题 + 判定分析深度"""

import json

from app.core.llm_client import llm_client

INTENT_SYSTEM_PROMPT = """你是一个企业数据分析助手的意图识别模块。根据用户问题和数据源结构，判断分析意图和难度。

输出格式 (严格 JSON):
{
  "intent": "simple_count | trend_analysis | comparison | prediction | anomaly_detection | root_cause | general",
  "entities": ["涉及的表名或字段"],
  "time_range": "时间范围，如 last_30_days, last_6_months, current_month",
  "analysis_depth": "simple | complex"
}

判定规则:
- simple: 单表筛选/计数/聚合/排序，单时间点数据
- complex: 多表关联、趋势分析、预测、异常检测、统计建模、根因分析
"""


async def detect_intent(question: str, schema_summary: dict | None) -> dict:
    """分析用户问题的意图和难度"""
    schema_text = json.dumps(schema_summary, ensure_ascii=False) if schema_summary else "数据源结构未探测"
    user_msg = f"数据源结构:\n{schema_text}\n\n用户问题: {question}"

    try:
        msg = await llm_client.chat([
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        content = msg.get("content", "{}")
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        return json.loads(content)
    except Exception:
        return {
            "intent": "general", "entities": [],
            "time_range": "unknown", "analysis_depth": "simple",
        }
