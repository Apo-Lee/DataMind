"""Agent 错误处理模块 — 友好、有洞察的错误响应

错误类型分类：
- IntentError:      看不懂问题 / 需要澄清
- PermissionError:  权限不够 / 敏感字段
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


# ============================================================
# 错误分析与友好消息生成
# ============================================================

ERROR_CATALOG = {
    # SQL 执行错误
    "no such column": AgentFriendlyError(
        AgentErrorType.SCHEMA_ERROR,
        "**😅 查询遇到了一点麻烦**",
        detail="SQL 中引用了不存在的列",
        suggestion="这可能是因为我尝试查询的列在数据库表中不存在。请换个方式描述你的问题。",
        followups=["查看我的部门有哪些员工？", "统计一下各部门的人数"],
    ),
    "no such table": AgentFriendlyError(
        AgentErrorType.SCHEMA_ERROR,
        "**😅 查询的表不存在**",
        detail="SQL 中引用了不存在的表",
        suggestion="我尝试查询的表不在当前数据库中。请确认你要查询哪个数据源。",
    ),
    "ambiguous column name": AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**🤔 查询需要更精确一些**",
        detail="多表关联时列名有歧义",
        suggestion="这个问题涉及多个表，列名存在重复。请使用更具体的描述，比如加上表名。",
        followups=["技术部的具体员工名单", "每个部门的人数统计"],
    ),
    # 执行超时
    "timeout": AgentFriendlyError(
        AgentErrorType.TIMEOUT_ERROR,
        "**⏱️ 查询时间较长，无法返回结果**",
        detail="查询超时",
        suggestion="数据量较大导致查询超时。请缩小查询范围，比如加上时间或部门筛选。",
        followups=["查看上个月的数据", "只看技术部的数据"],
    ),
    # SQL 语法
    "syntax error": AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**😅 查询语法有问题**",
        detail="生成的 SQL 语法错误",
        suggestion="我生成的查询语句有语法问题。请换个说法重新描述你的问题。",
    ),
    # 值不存在
    "no such": AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**🔍 没有找到匹配的数据**",
        detail="查询条件匹配不到数据",
        suggestion="试试调整查询条件，比如换个时间范围或筛选条件。",
        followups=["查看所有部门的数据", "换个时间范围查询"],
    ),
    "MAT-": AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**🔍 查询条件可能不太对**",
        detail="提供的筛选值在数据库中不存在",
        suggestion="你提到的特定值在数据库中找不到。试试用更常见的分类来查询。",
        followups=["查看所有项目", "统计部门费用"],
    ),
}


def classify_sql_error(error_msg: str) -> Optional[AgentFriendlyError]:
    """根据 SQL 错误信息分类并返回友好的错误响应"""
    if not error_msg:
        return None

    error_lower = error_msg.lower()

    for keyword, friendly_error in ERROR_CATALOG.items():
        if keyword.lower() in error_lower:
            return friendly_error

    return None


def make_friendly_permission_error(reason: str) -> AgentFriendlyError:
    """生成权限错误的友好消息"""
    if "highly_sensitive" in reason.lower() or "salary" in reason.lower():
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**🔒 无权查看薪资数据**",
            detail=reason,
            suggestion="薪资信息属于高度敏感数据，你的角色暂无权限查看。可以查询其他非敏感数据。",
            followups=["查看我的绩效评分", "统计各部门人数", "查询出勤率"],
        )
    if "sensitive" in reason.lower():
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**🔒 无权查看该数据**",
            detail=reason,
            suggestion="这些字段属于敏感信息，你的角色暂无访问权限。",
            followups=["查看可访问的数据", "统计各部门人数"],
        )
    if "员工角色不能" in reason:
        return AgentFriendlyError(
            AgentErrorType.PERMISSION_ERROR,
            "**🔒 该操作需要更高权限**",
            detail=reason,
            suggestion="作为普通员工，你可以查看自己的数据，但不能做全公司的聚合统计。试试查看个人数据。",
            followups=["我这个月的出勤情况", "我的绩效评分"],
        )

    return AgentFriendlyError(
        AgentErrorType.PERMISSION_ERROR,
        "**🔒 权限不足**",
        detail=reason,
        suggestion="当前角色的权限不足以执行这个查询。如需更高权限请联系管理员。",
        followups=["查看我有权限的数据", "查看我的个人信息"],
    )


def make_friendly_intent_error(detail: str) -> AgentFriendlyError:
    """意图识别错误的友好消息"""
    return AgentFriendlyError(
        AgentErrorType.INTENT_ERROR,
        "**🤔 我没完全理解你的问题**",
        detail=detail,
        suggestion="请用更明确的方式描述你想查什么，比如：\n- 「技术部有多少员工」\n- 「上个月各部门的出勤率」\n- 「我的绩效评分是多少」",
        followups=["技术部有多少员工", "上个月各部门的出勤率", "我的绩效评分是多少"],
    )


def make_friendly_query_error(detail: str, sql: str = "") -> AgentFriendlyError:
    """查询执行错误的友好消息"""
    # 先尝试从 SQL 错误信息分类
    classified = classify_sql_error(detail)
    if classified:
        return classified

    return AgentFriendlyError(
        AgentErrorType.QUERY_ERROR,
        "**😅 查询执行时遇到问题**",
        detail=f"{detail} | SQL: {sql[:100]}" if sql else detail,
        suggestion="请换个方式描述你的问题，或者试试更简单的查询。",
        followups=["看看有哪些数据可查", "统计各部门人数"],
    )


def make_friendly_analysis_error(detail: str) -> AgentFriendlyError:
    """分析错误的友好消息"""
    return AgentFriendlyError(
        AgentErrorType.ANALYSIS_ERROR,
        "**📊 深度分析遇到问题**",
        detail=detail,
        suggestion="深度分析暂时不可用，不过我已经完成了基础数据查询，你可以直接查看表格结果。",
        followups=["查看数据表格", "换个角度分析"],
    )


def make_friendly_error(error_type: str, detail: str, sql: str = "") -> AgentFriendlyError:
    """统一入口：根据错误类型生成友好错误"""
    if "intent" in error_type.lower():
        return make_friendly_intent_error(detail)
    if "permission" in error_type.lower():
        return make_friendly_permission_error(detail)
    if "sql" in error_type.lower() or "query" in error_type.lower():
        return make_friendly_query_error(detail, sql)
    if "analysis" in error_type.lower():
        return make_friendly_analysis_error(detail)
    # 默认
    return AgentFriendlyError(
        AgentErrorType.UNKNOWN_ERROR,
        "**😅 系统遇到意外错误**",
        detail=f"{error_type}: {detail}",
        suggestion="请稍后重试，或者换个问题试试。",
        followups=["看看有哪些数据可查", "我的个人信息"],
    )
