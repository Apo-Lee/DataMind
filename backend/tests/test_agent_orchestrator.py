"""LangGraph Agent 单元测试"""
import sys
sys.path.insert(0, "E:\\Python_Code_Project\\DataMind\\backend")

import pytest
from app.orchestrator.state import (
    AgentState, AgentContext, IntentResult, SQLResult, AnalysisResult, ReportResult,
    IntentType, route_by_intent, route_after_sql,
)


class TestAgentRouting:
    """测试 LangGraph 条件路由逻辑"""

    def test_intent_greeting_routes_to_report(self):
        """greeting 意图应直接到 report_node"""
        state = AgentState(
            question="你好",
            intent_result=IntentResult(
                status="success",
                intent_type=IntentType.greeting,
                analysis_depth="simple",
            ),
            context=AgentContext(),
        )
        assert route_by_intent(state) == "report_node"

    def test_intent_help_routes_to_report(self):
        state = AgentState(
            question="你能做什么",
            intent_result=IntentResult(
                status="success",
                intent_type=IntentType.help,
                analysis_depth="simple",
            ),
            context=AgentContext(),
        )
        assert route_by_intent(state) == "report_node"

    def test_intent_unknown_routes_to_sql(self):
        state = AgentState(
            question="上月销售额多少",
            intent_result=IntentResult(
                status="success",
                intent_type=IntentType.direct_query,
                analysis_depth="simple",
            ),
            context=AgentContext(),
        )
        assert route_by_intent(state) == "sql_node"

    def test_intent_trend_routes_to_sql(self):
        state = AgentState(
            question="近6个月趋势",
            intent_result=IntentResult(
                status="success",
                intent_type=IntentType.trend,
                analysis_depth="complex",
            ),
            context=AgentContext(),
        )
        assert route_by_intent(state) == "sql_node"

    def test_intent_root_cause_routes_to_analysis(self):
        state = AgentState(
            question="为什么下降",
            intent_result=IntentResult(
                status="success",
                intent_type=IntentType.root_cause,
                analysis_depth="complex",
            ),
            context=AgentContext(),
        )
        assert route_by_intent(state) == "analysis_node"

    def test_route_after_sql_complex_goes_to_analysis(self):
        """SQL 查询后，complex 意图且有数据 → analysis_node"""
        import pandas as pd
        state = AgentState(
            question="对比各部门出勤率",
            intent_result=IntentResult(
                status="success", intent_type=IntentType.comparison,
                analysis_depth="complex",
            ),
            sql_result=SQLResult(
                status="success", sql="SELECT ...",
                df=pd.DataFrame({"dept": ["A"], "rate": [0.95]}),
            ),
        )
        assert route_after_sql(state) == "analysis_node"

    def test_route_after_sql_simple_goes_to_report(self):
        """SQL 查询后，simple 意图 → report_node"""
        import pandas as pd
        state = AgentState(
            question="本月销售额",
            intent_result=IntentResult(
                status="success", intent_type=IntentType.direct_query,
                analysis_depth="simple",
            ),
            sql_result=SQLResult(
                status="success", sql="SELECT ...",
                df=pd.DataFrame({"amount": [100]}),
            ),
        )
        assert route_after_sql(state) == "report_node"

    def test_route_after_sql_empty_data_goes_to_report(self):
        """SQL 结果为空 → report_node"""
        import pandas as pd
        state = AgentState(
            question="复杂查询",
            intent_result=IntentResult(
                status="success", intent_type=IntentType.trend,
                analysis_depth="complex",
            ),
            sql_result=SQLResult(
                status="success", sql="SELECT ...",
                df=pd.DataFrame(),
            ),
        )
        assert route_after_sql(state) == "report_node"

    def test_intent_result_none_fallback_to_sql(self):
        state = AgentState(
            question="test",
            context=AgentContext(),
        )
        assert route_by_intent(state) == "sql_node"

    def test_intent_result_error_fallback_to_sql(self):
        state = AgentState(
            question="test",
            intent_result=IntentResult(status="error", error="failed"),
            context=AgentContext(),
        )
        assert route_by_intent(state) == "sql_node"


class TestAgentStateSchema:
    """测试 AgentState 数据完整性"""

    def test_full_agent_state(self):
        import pandas as pd
        state = AgentState(
            question="测试问题",
            context=AgentContext(
                user_role="dept_manager",
                user_data_scope="dept",
                session_id="test-session",
                turn_number=1,
            ),
            intent_result=IntentResult(
                status="success",
                intent_type=IntentType.aggregation,
                intent_label="聚合查询",
                analysis_depth="simple",
                entities=["employees", "salary"],
                confidence=0.95,
            ),
            sql_result=SQLResult(
                status="success",
                sql="SELECT dept_id, AVG(salary) FROM employees GROUP BY dept_id",
                df=pd.DataFrame({"dept_id": [1, 2], "avg_salary": [10000, 15000]}),
                rows_affected=2,
                execution_time_ms=45,
            ),
            report_result=ReportResult(
                status="success",
                report_markdown="## 分析结果\n各部门平均薪资: ...",
                insights=[{"type": "table", "content": [{"dept_id": 1, "avg_salary": 10000}]}],
                followups=["按部门查看详情？", "查看趋势变化？"],
            ),
        )
        assert state["question"] == "测试问题"
        assert state["context"].user_role == "dept_manager"
        assert state["intent_result"].intent_type == IntentType.aggregation
        assert state["sql_result"].rows_affected == 2
        assert len(state["report_result"].followups) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
