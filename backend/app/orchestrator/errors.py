"""Agent 错误处理模块 — 有温度、有洞察的友好错误响应

错误类型分类：
- IntentError:      看不懂问题 / 需要澄清
- PermissionError:  权限不够 / 敏感字段 / 无数据源
- SchemaError:      表/列不存在
- QueryError:       SQL 语法错误 / 数据为空
- AnalysisError:    分析失败（沙箱/LLM）
- TimeoutError:     超时
- UnknownError:     未知
"""

from enum import Enum
from typing import Optional


class AgentErrorType(str, Enum):
    INTENT_ERROR = "intent_error"
    PERMISSION_ERROR = "permission_error"
    SCHEMA_ERROR = "schema_error"
    QUERY_ERROR = "query_error"
    ANALYSIS_ERROR = "analysis_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


class AgentFriendlyError(Exception):
    """带有用户友好的中文消息的 Agent 异常"""

    def __init__(
        self,
        error_type: AgentErrorType,
        message: str,                     # 面向用户的友好消息
        detail: str = "",                 # 技术细节（日志用）
        suggestion: str = "",             # 给用户的建议
        followups: list[str] = None,      # 追问建议
    ):
        self.error_type = error_type
        self.message = message
        self.detail = detail or message
        self.suggestion = suggestion
        self.followups = followups or []
        super().__init__(self.message)

    def to_user_response(self) -> dict:
        """生成给用户的友好响应"""
        report_parts = [self.message]
        if self.suggestion:
            report_parts.append("")
            report_parts.append("**💡 建议**: " + self.suggestion)
        if self.followups:
            report_parts.append("")
            report_parts.append("**试试问**:")
            for f in self.followups:
                report_parts.append("- " + f)

        return {
            "report_markdown": "\n".join(report_parts),
            "insights": [],
            "followups": self.followups,
            "error_type": self.error_type.value,
            "error": self.detail,
        }


def _make_role_aware_suggestion(role: str | None, action_type: str) -> str:
    """根据用户角色和操作类型生成精准建议"""
    role_suggestions = {
        "employee": {
            "permission": "作为普通员工，你可以查询自己的数据。试试查我自己的出勤、绩效或个人信息。",
            "no_data": "你的角色只能看到自己的数据，可能是当前条件下没有匹配的记录。",
            "general": "你可以查询自己的数据，比如出勤记录、绩效评分。",
        },
        "dept_manager": {
            "permission": "作为部门经理，你可以查看本部门的数据。试试查询部门的人员统计或预算情况。",
            "no_data": "当前部门范围内没有匹配的数据，试试换个筛选条件。",
            "general": "你可以查询本部门的员工数据、考勤统计和预算信息。",
        },
        "sales_manager": {
            "permission": "作为销售经理，你可以查看自己及下属团队的数据。",
            "no_data": "当前团队范围内没有匹配的数据，试试扩大查询范围。",
            "general": "你可以查询团队的销售业绩、客户跟进情况。",
        },
        "finance_bp": {
            "permission": "作为财务BP，你可以查看所负责部门的预算和费用数据。",
            "no_data": "当前部门范围内没有匹配的财务数据，试试换个时间范围。",
            "general": "你可以查询预算使用情况、费用支出和成本中心数据。",
        },
        "dept_ceo": {
            "permission": "作为部门CEO，你可以查看本部门及下属的所有数据。",
            "no_data": "当前范围内没有匹配的数据，试试换个维度查看。",
            "general": "你可以查看部门的全景数据：人力、财务、项目进度。",
        },
        "hr_director": {
            "permission": "作为HR总监，你可以查看全公司的HR数据（敏感字段已脱敏）。",
            "no_data": "没有匹配的HR数据，试试调整查询条件。",
            "general": "你可以查询全公司的组织架构、员工统计、绩效数据。",
        },
        "admin": {
            "permission": "作为管理员，你有全系统最高权限，可直接查询任意数据。",
            "no_data": "没有匹配的数据，试试调整查询条件或确认数据源中是否有内容。",
            "general": "你有全系统权限，可以查询任意数据源。",
        },
    }
    role_key = role if role in role_suggestions else "employee"
    return role_suggestions[role_key].get(action_type, role_suggestions[role_key]["general"])


# ============================================================
# 错误分析与友好消息生成
# ============================================================

ERROR_CATALOG = {
    # --- SQL 执行错误 ---
    "no such column": lambda role: AgentFriendlyError(
        AgentErrorType.SCHEMA_ERROR,
        "**😅 查询的字段不存在**",
        detail="SQL 中引用了不存在的列",
        suggestion="我尝试查询的列名在数据库中不存在。可能是字段名称和你想的不太一样，请换个方式描述。"
                   if not role else _make_role_aware_suggestion(role, "general"),
        followups=["查看我的部门有哪些员工？", "统计一下各部门的人数"],
    ),
    "no such table": lambda role: AgentFriendlyError(
        AgentErrorType.SCHEMA_ERROR,
        "**😅 查询的表不存在**",
        detail="SQL 中引用了不存在的表",
        suggestion="我查询的表不在当前数据源中。请确认你要查的是哪个数据源（HR/财务/CRM/ERP）。",
        followups=["查看HR数据", "查看财务数据"],
    ),
    "ambiguous column name": lambda role: AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**🤔 查询需要更精确一些**",
        detail="多表关联时列名有歧义",
        suggestion="这个问题涉及多个表，列名存在重复。请用更具体的描述，比如把「部门」改成「部门的名称」。",
        followups=["技术部的具体员工名单", "每个部门的人数统计"],
    ),
    # --- 空结果 ---
    "no data": lambda role: AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**📭 没有找到匹配的数据**",
        detail="查询结果为空",
        suggestion=_make_role_aware_suggestion(role, "no_data") if role else "试试调整查询条件，换个时间范围或筛选条件。",
        followups=["查看所有部门的数据"] if role != "employee" else ["查看我的个人信息"],
    ),
    # --- 超时 ---
    "timeout": lambda role: AgentFriendlyError(
        AgentErrorType.TIMEOUT_ERROR,
        "**⏱️ 查询时间较长，无法返回结果**",
        detail="查询超时",
        suggestion="数据量较大导致查询超时。请缩小查询范围，比如加上时间或部门筛选。",
        followups=["查看上个月的数据", "只看技术部的数据"],
    ),
    # --- SQL 语法 ---
    "syntax error": lambda role: AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**😅 查询语法有问题**",
        detail="生成的 SQL 语法错误",
        suggestion="我生成的查询语句有语法问题。请换个说法重新描述你的问题。",
    ),
    # --- 值不存在 ---
    "no such": lambda role: AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**🔍 没有找到匹配的数据**",
        detail="查询条件匹配不到数据",
        suggestion="试试调整查询条件，比如换个时间范围或筛选条件。",
        followups=["查看所有部门的数据", "换个时间范围查询"],
    ),
    "MAT-": lambda role: AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**🔍 查询条件可能不太对**",
        detail="提供的筛选值在数据库中不存在",
        suggestion="你提到的特定值在数据库中找不到。试试用更常见的分类来查询。",
        followups=["查看所有项目", "统计部门费用"],
    ),
}


def classify_sql_error(error_msg: str, role: str | None = None) -> Optional[AgentFriendlyError]:
    """根据 SQL 错误信息分类并返回友好的错误响应"""
    if not error_msg:
        return None

    error_lower = error_msg.lower()

    for keyword, factory_fn in ERROR_CATALOG.items():
        if keyword.lower() in error_lower:
            return factory_fn(role)

    return None


def make_friendly_permission_error(reason: str, role: str | None = None) -> AgentFriendlyError:
    """生成权限错误的友好消息（带角色感知）"""
    role_ctx = _make_role_aware_suggestion(role, "permission") if role else ""

    # 列级脱敏
    if "highly_sensitive" in reason.lower() or "salary" in reason.lower():
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**🔒 无权查看薪资数据**",
            detail=reason,
            suggestion=f"薪资信息属于高度敏感数据，你的角色暂无权限查看。{role_ctx}",
            followups=["查看我的个人绩效评分", "统计各部门人数", "查询出勤率"],
        )
    if "sensitive" in reason.lower():
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**🔒 无权查看该敏感数据**",
            detail=reason,
            suggestion=f"这些字段属于敏感信息，你的角色暂无访问权限。{role_ctx}",
            followups=["查看可访问的数据", "统计各部门人数"],
        )

    # 表级阻断
    if "access denied" in reason.lower():
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**🚫 无权访问该数据**",
            detail=reason,
            suggestion=f"你当前的角色没有权限查看这张表。{role_ctx}",
            followups=["看看我能查什么", "查看我的个人信息"],
        )

    # 无数据源
    if "datasource" in reason.lower() or "数据源" in reason:
        if role == "admin":
            return AgentFriendlyError(
                AgentErrorType.PERMISSION_ERROR,
                "**📡 数据源未找到**",
                detail=reason,
                suggestion="当前系统没有检测到匹配的数据源，或者数据源已停用。请前往「数据源管理」检查配置。",
                followups=["查看所有数据源", "配置新的数据源"],
            )
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**📡 数据源不可用**",
            detail=reason,
            suggestion="你要查的数据源当前不可用，或者没有匹配的数据源。请联系管理员确认数据源配置。",
            followups=["查看我有权限的数据源"],
        )

    # 通用权限不足
    return AgentFriendlyError(
        AgentErrorType.PERMISSION_ERROR,
        "**🔒 权限不足**",
        detail=reason,
        suggestion=role_ctx or "当前角色的权限不足以执行这个查询。如需更高权限请联系管理员。",
        followups=["查看我有权限的数据", "查看我的个人信息"],
    )


def make_friendly_intent_error(detail: str, role: str | None = None) -> AgentFriendlyError:
    """意图识别错误的友好消息（带角色感知）"""
    role_suffix = ""
    if role:
        role_suffix = _make_role_aware_suggestion(role, "general")
        role_suffix = f"\n\n{role_suffix}"

    return AgentFriendlyError(
        AgentErrorType.INTENT_ERROR,
        "**🤔 我没完全理解你的问题**",
        detail=detail,
        suggestion=f"请用更明确的方式描述你想查什么，比如：{role_suffix}\n\n"
                   "常见问法：\n"
                   "- 「技术部有多少员工」（查具体数据）\n"
                   "- 「上个月各部门的出勤率」（统计汇总）\n"
                   "- 「近半年的销售趋势」（趋势分析）\n"
                   "- 「为什么费用超支了」（根因分析）",
        followups=[
            "技术部有多少员工",
            "上个月各部门的出勤率",
            "近半年的销售趋势",
        ],
    )


def make_friendly_query_error(detail: str, sql: str = "", role: str | None = None) -> AgentFriendlyError:
    """查询执行错误的友好消息"""
    # 先尝试从 SQL 错误信息分类
    classified = classify_sql_error(detail, role)
    if classified:
        return classified

    return AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**😅 查询执行时遇到问题**",
        detail=f"{detail} | SQL: {sql[:100]}" if sql else detail,
        suggestion="请换个方式描述你的问题，或者试试更简单的查询。",
        followups=["看看有哪些数据可查", "统计各部门人数"],
    )


def make_friendly_analysis_error(detail: str, role: str | None = None) -> AgentFriendlyError:
    """分析错误的友好消息"""
    return AgentFriendlyError(
        AgentErrorType.ANALYSIS_ERROR,
        "**📊 深度分析遇到问题**",
        detail=detail,
        suggestion="深度分析暂时不可用，不过我已经完成了基础数据查询，你可以直接查看表格结果。",
        followups=["查看数据表格", "换个角度分析"],
    )


def make_friendly_no_datasource_error(user_role: str | None = None) -> AgentFriendlyError:
    """没有可用数据源的错误消息"""
    if user_role == "admin":
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**📡 没有可用的数据源**",
            detail="系统未配置数据源",
            suggestion="当前系统没有配置任何数据源。请前往「数据源管理」页面添加数据源后再使用。\n\n"
                      "添加步骤：\n"
                      "1. 点击左侧「数据源管理」\n"
                      "2. 点击「新增数据源」\n"
                      "3. 填写数据库连接信息并保存",
            followups=["前往数据源管理"],
        )
    if user_role == "viewer":
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**👀 只读用户暂无可访问的数据源**",
            detail="viewer 角色未分配数据源权限",
            suggestion="你的账号是只读角色，目前没有分配任何数据源的访问权限。请联系管理员为你分配。",
            followups=[],
        )
    return AgentFriendlyError(
        AgentErrorType.PERMISSION_ERROR,
        "**📡 没有可用的数据源**",
        detail="系统未配置数据源或用户无权限",
        suggestion="当前没有你可以访问的数据源。可能是系统未配置数据源，或者你的账号没有被分配数据源权限。\n\n"
                  "请联系管理员确认：\n"
                  "1. 是否已添加数据源\n"
                  "2. 你的账号是否已有数据源权限",
        followups=["查看我的账号信息"],
    )


def make_friendly_data_empty_error(question: str, role: str | None = None) -> AgentFriendlyError:
    """查询结果为空时的友好消息（带业务上下文）"""
    context_help = ""
    if "费用" in question or "支出" in question or "预算" in question:
        context_help = "可能是当前月份还没有费用记录，或者筛选条件过严格。"
    elif "出勤" in question or "考勤" in question:
        context_help = "可能是当月考勤数据还未录入，或者你的筛选范围没有员工。"
    elif "销售" in question or "业绩" in question or "成交" in question:
        context_help = "可能是该时间段没有成交记录，试试扩大时间范围。"
    elif "员工" in question or "人员" in question or "人力" in question:
        context_help = "可能是当前部门的员工数据为空，或者查询条件需要调整。"
    else:
        context_help = "试试换个时间范围或筛选条件，或者换个数据源查询。"

    role_ctx = _make_role_aware_suggestion(role, "no_data") if role else ""

    return AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**📭 查询完成，没有找到记录**",
        detail=f"问题「{question}」查询结果为空",
        suggestion=f"{context_help}\n{role_ctx}" if role_ctx else context_help,
        followups=["查看所有数据", "换个时间范围查询"],
    )


def make_friendly_error(error_type: str, detail: str, sql: str = "", role: str | None = None) -> AgentFriendlyError:
    """统一入口：根据错误类型生成友好错误"""
    if "intent" in error_type.lower():
        return make_friendly_intent_error(detail, role)
    if "permission" in error_type.lower():
        return make_friendly_permission_error(detail, role)
    if "no_datasource" in error_type.lower() or "datasource" in error_type.lower():
        return make_friendly_no_datasource_error(role)
    if "sql" in error_type.lower() or "query" in error_type.lower():
        return make_friendly_query_error(detail, sql, role)
    if "analysis" in error_type.lower():
        return make_friendly_analysis_error(detail, role)
    # 默认
    return AgentFriendlyError(
        AgentErrorType.UNKNOWN_ERROR,
        "**😅 系统遇到意外错误**",
        detail=f"{error_type}: {detail}",
        suggestion="请稍后重试，或者换个问题试试。",
        followups=["看看有哪些数据可查", "我的个人信息"],
    )