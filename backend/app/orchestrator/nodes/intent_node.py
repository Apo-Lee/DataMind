"""Intent Router Node — 增强版 15 类意图识别 + 追问检测"""

import json
import logging
import re

from app.core.llm_client import llm_client
from app.orchestrator.state import (
    AgentState, AgentContext, IntentResult, IntentResult as IntentNodeResult,
    IntentType, route_by_intent,
)

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT_V2 = """你是一个企业数据分析助手的意图识别专家。根据用户问题、数据源结构和对话历史，判断分析意图。

意图类型精确定义（请严格区分）:

**直查类 (返回具体数值/记录)**：
- direct_query: 用户问一个具体数值或事实，不涉及计算。如"上月份销售额是多少"、"技术部有多少人"
- list_query: 用户要求列出所有项目。如"列出所有部门"、"有哪些客户"
- aggregation: 用户明确要求计算平均值/总和/比率。如"平均出勤率是多少"、"各部门平均薪资"

**分析类 (涉及多维度/跨时间/统计建模)**：
- trend: 时间趋势分析。如"近6个月变化趋势"、"月度增长情况"
- comparison: 实体间对比。如"对比A和B"、"哪个部门最高"
- ranking: 排行。如"Top 10"、"排前三的"
- distribution: 分布。如"学历分布"、"年龄段占比"
- anomaly: 异常检测。如"哪些数据异常"
- root_cause: 根因分析。如"为什么下降"、"原因是什么"
- forecast: 预测。如"下季度预测"

**交互类**：
- drill_down: 追问细化。如"具体看xx"、"展开说说"
- refinement: 改变粒度。如"改成按月份"、"按部门分组"
- cross_domain: 跨域。如"对比HR和CRM"

**元类**：
- greeting: 纯问候。如"你好"、"在吗"
- help: 询问能力。如"你能做什么"

特别注意:
- "上月份总销售额" → direct_query (问具体数值), 而非 aggregation
- "各部门平均薪资" → aggregation (明确"平均"), 而非 direct_query
- 只有明确包含"平均/总计/合计/求和"等计算关键词时才用 aggregation

输出严格 JSON 格式（不要附带其他文字）:
{
    "intent_type": "direct_query | list_query | aggregation | trend | comparison | ranking | distribution | anomaly | root_cause | forecast | drill_down | refinement | cross_domain | greeting | help | unknown",
    "intent_label": "简短的中文意图描述，如'查询销售额'",
    "analysis_depth": "simple | complex",
    "entities": ["涉及的表名或字段"],
    "time_range": "last_30_days | last_6_months | current_month | last_year | unknown",
    "confidence": 0.0-1.0,
    "needs_clarification": false,
    "clarification_question": "如果问题有歧义，提出澄清问题"
}

判定规则:
- simple: 单表筛选/计数/聚合/排序，单时间点数据
- complex: 多表关联、趋势分析、预测、异常检测、统计建模、根因分析、对比分析
- greeting: 用户打招呼、问候
- help: 询问能力范围
- drill_down: 对前一问题的进一步细化追问
- refinement: 改变展示粒度（按天→按月）
- cross_domain: 涉及多个数据源
"""


def _build_context_prompt(context: AgentContext | None, turn_history: list[dict]) -> str:
    """构建上下文信息给 LLM"""
    parts = []

    if turn_history:
        parts.append("【历史对话摘要】")
        for i, turn in enumerate(turn_history[-3:]):  # 最近3轮
            parts.append(f"  第{i+1}轮: 『{turn.get('question', '')}』→ intent={turn.get('intent', '')}")

    if context:
        parts.append(f"【当前用户】角色={context.user_role}, 数据范围={context.user_data_scope}")
        parts.append(f"【数据源】ID={context.datasource_id}, 业务标签={context.business_tag}")
        if context.is_followup:
            parts.append("【追问检测】这是对上一轮的追问")

    return "\n".join(parts)


def _is_followup(question: str, turn_history: list[dict]) -> bool:
    """基于规则的追问检测（零成本，无需调 LLM）"""
    if not turn_history:
        return False

    followup_markers = [
        "具体", "详细", "展开", "深入", "再说", "进一步",
        "那", "那么", "再", "还有", "另外", "对比",
        "为什么", "原因", "解释", "怎么看",
        "按", "分", "按照", "改成", "改为",
    ]
    for marker in followup_markers:
        if marker in question:
            return True

    last_q = turn_history[-1].get("question", "")
    # 如果问题很短且包含上次问题中的实体词，判定为追问
    if len(question) < 10 and len(last_q) > 5:
        shared_chars = set(question) & set(last_q)
        if len(shared_chars) >= 2:
            return True

    return False


async def intent_node(state: AgentState) -> dict:
    """意图识别节点 — LangGraph Node"""
    context: AgentContext | None = state.get("context")
    question = state.get("question", "")
    turn_history = state.get("turn_history", [])
    retry_count = state.get("retry_count", 0)

    # 规则：问候语快速判断
    greeting_patterns = ["你好", "您好", "hi", "hello", "hey", "在吗", "在不在"]
    if question.strip() in greeting_patterns or question.strip().lower() in [g.lower() for g in greeting_patterns]:
        return {
            "intent_result": IntentNodeResult(
                status="success",
                intent_type=IntentType.greeting,
                intent_label="问候",
                analysis_depth="simple",
                confidence=1.0,
            ),
        }

    is_followup = _is_followup(question, turn_history)

    context_prompt = _build_context_prompt(context, turn_history)
    user_msg = f"{context_prompt}\n\n用户问题: {question}" + (
        "\n\n注意: 这是对前一问题的追问" if is_followup else ""
    )

    try:
        msg = await llm_client.chat([
            {"role": "system", "content": INTENT_SYSTEM_PROMPT_V2},
            {"role": "user", "content": user_msg},
        ])
        content = msg.get("content", "{}").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]

        data = json.loads(content)
        intent_type_str = data.get("intent_type", "unknown")

        # 验证 intent_type 合法性
        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.unknown

        return {
            "intent_result": IntentNodeResult(
                status="success",
                intent_type=intent_type,
                intent_label=data.get("intent_label", "未知"),
                analysis_depth=data.get("analysis_depth", "simple"),
                entities=data.get("entities", []),
                time_range=data.get("time_range", "unknown"),
                confidence=data.get("confidence", 0.5),
                needs_clarification=data.get("needs_clarification", False),
                clarification_question=data.get("clarification_question"),
            ),
        }
    except Exception as e:
        logger.warning(f"Intent LLM 调用失败 (重试={retry_count}): {e}")
        return {
            "intent_result": IntentNodeResult(
                status="error",
                error=f"意图识别失败: {e}",
                error_type="IntentError",
            ),
        }
