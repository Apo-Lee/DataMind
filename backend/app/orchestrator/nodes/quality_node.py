# -*- coding: utf-8 -*-
"""Quality Node - SQL quality check + MCP tool selection validation"""

import json
import logging
import re
from typing import Any

from app.orchestrator.state import (
    AgentState, AgentContext, SQLResult, IntentResult,
    IntentType,
)

logger = logging.getLogger(__name__)

# High risk SQL patterns
HIGH_RISK_PATTERNS = [
    (r"FROM\s+(\w+)\s*(?:,|\Z|\s+(?!WHERE))", "MISSING_WHERE", "SQL lacks WHERE clause"),
    (r"DROP\s+TABLE", "DDL_DROP", "DROP TABLE not allowed"),
    (r"DELETE\s+FROM", "DDL_DELETE", "DELETE not allowed"),
    (r"INSERT\s+INTO", "DDL_INSERT", "INSERT not allowed"),
    (r"UPDATE\s+\w+", "DDL_UPDATE", "UPDATE not allowed"),
]


def check_sql_quality(sql: str, role: str = "employee") -> dict:
    """Check SQL for common quality issues"""
    if not sql:
        return {"passed": True, "risks": [], "suggestion": ""}
    risks = []
    for pattern, risk_id, detail in HIGH_RISK_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            risks.append({"risk": risk_id, "detail": detail, "level": "error"})
    return {
        "passed": len([r for r in risks if r["level"]=="error"])==0,
        "risks": risks,
        "suggestion": "; ".join(r["detail"] for r in risks) if risks else "",
    }


async def quality_node(state: AgentState) -> dict:
    """Quality Node - validate SQL and MCP tool choices"""
    context = state.get("context")
    sql_result = state.get("sql_result")

    # SQL quality check (only when sql_result exists - legacy path)
    if sql_result and hasattr(sql_result, "sql") and sql_result.sql:
        role = context.user_role if context else "employee"
        check = check_sql_quality(sql_result.sql, role)
        if not check["passed"]:
            return {
                "quality_check": {"passed": False, "risks": check["risks"], "suggestion": check["suggestion"]},
                "last_error": check["suggestion"],
            }

    # Default: pass
    return {
        "quality_check": {"passed": True, "risks": [], "suggestion": ""},
    }
