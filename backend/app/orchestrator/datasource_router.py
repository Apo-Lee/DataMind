"""
数据源自动检测模块 — 根据用户问题智能路由到最匹配的数据源
"""

import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import DataSource
from app.models.user import User

logger = logging.getLogger(__name__)

DATASOURCE_DETECTION_PROMPT = """你是一个数据源路由专家。根据用户问题，从以下数据源中选择最匹配的一个。

数据源列表:
{datasource_list}

判断规则:
1. 费用/报销/预算相关 → finance
2. 员工/部门/考勤/薪资相关 → hr
3. 客户/商机/合同相关 → crm
4. 采购/库存/供应链相关 → erp
5. 如果问题不明确，选择 "unknown"
6. 如果问题明显属于多个数据源，选择最相关的一个

输出严格 JSON 格式（不要附带其他文字）:
{{"datasource":"hr|crm|finance|erp|unknown","reason":"简短的中文判断理由"}}

用户问题: {question}
"""


async def detect_datasource(question: str, user: User, db: AsyncSession) -> tuple[Optional[str], Optional[str], str]:
    """根据用户问题自动检测最匹配的数据源

    Returns:
        (datasource_id, business_tag, reason)
    """
    # 获取用户有权限访问的数据源
    result = await db.execute(
        select(DataSource).where(DataSource.is_active == True)
    )
    dss = result.scalars().all()

    if not dss:
        return None, None, "没有可用的数据源"

    if len(dss) == 1:
        return dss[0].id, dss[0].business_tag, f"唯一数据源: {dss[0].name}"

    # 构建数据源列表文本
    ds_lines = []
    tag_names = {"hr": "HR系统（员工信息、部门、考勤、薪资）",
                 "crm": "CRM系统（客户、商机、合同、回款）",
                 "finance": "费控系统（费用报销、预算、差旅）",
                 "erp": "ERP系统（采购、库存、生产、供应链）"}
    for ds in dss:
        desc = tag_names.get(ds.business_tag, ds.business_tag)
        ds_lines.append(f"- {ds.business_tag}: {ds.name} — {desc}")
    ds_text = "\n".join(ds_lines)

    prompt = DATASOURCE_DETECTION_PROMPT.format(
        datasource_list=ds_text,
        question=question
    )

    from app.core.llm_client import llm_client

    try:
        msg = await llm_client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ])
        content = msg.get("content", "").strip()

        if content.startswith("```"):
            lines = content.split("\n", 1)
            if len(lines) > 1:
                content = lines[1]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].strip()

        data = json.loads(content)
        detected_tag = data.get("datasource", "unknown")
        reason = data.get("reason", "")

        # 查找匹配的数据源
        for ds in dss:
            if ds.business_tag == detected_tag:
                return ds.id, ds.business_tag, reason

        # 未匹配到，返回第一个数据源
        return dss[0].id, dss[0].business_tag, f"未明确匹配，默认使用: {dss[0].name}"
    except Exception as e:
        logger.warning(f"数据源自动检测失败: {e}")
        return dss[0].id, dss[0].business_tag, "检测失败，使用默认数据源"
