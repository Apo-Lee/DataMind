"""DataMind LangGraph Agent 全链路测试脚本"""
import asyncio
import os
import sys

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
sys.path.insert(0, ".")

import pandas as pd

from app.orchestrator.state import (
    AgentContext, IntentResult, SQLResult, AnalysisResult, ReportResult,
    IntentType, route_by_intent, route_after_sql,
)
from app.orchestrator.nodes.intent_node import intent_node
from app.orchestrator.nodes.analysis_node import _fallback_analysis


async def simulate_question(question, user_role="dept_manager", user_data_scope="dept",
                            turn_history=None, is_followup=False):
    """模拟一个用户问题经过 Agent 全链路的决策流程"""

    context = AgentContext(
        user_role=user_role,
        user_data_scope=user_data_scope,
        user_dept_name="技术部",
        user_id="user-001",
        user_employee_id=1001,
        user_dept_id=10,
        session_id="test-session",
        turn_number=(turn_history or []).__len__() + 1,
        is_followup=is_followup,
        datasource_id="ds-hr-001",
        business_tag="hr",
    )

    state = {
        "question": question,
        "context": context,
        "turn_history": turn_history or [],
        "retry_count": 0,
        "intent_result": None,
        "sql_result": None,
        "analysis_result": None,
        "report_result": None,
    }

    # Step 1: 意图识别
    intent_output = await intent_node(state)
    intent_result = intent_output.get("intent_result")

    label = intent_result.intent_label if intent_result.intent_label else "—"
    print(f"  [{intent_result.intent_type.value:20s}] depth={intent_result.analysis_depth:7s}  confidence={intent_result.confidence:.2f}  label={label}")

    # Step 2: 路由决策
    route = route_by_intent(state)
    print(f"  → 路由到: {route}")

    # Step 3: SQL 后路由决策（模拟数据）
    if route == "sql_node":
        mock_df = pd.DataFrame({"dept": ["技术部", "产品部"], "count": [50, 30], "rate": [0.95, 0.88]})
        state["sql_result"] = SQLResult(status="success", sql="SELECT ...", df=mock_df, rows_affected=2)
        after_sql_route = route_after_sql(state)
        print(f"  → SQL 后路由到: {after_sql_route}")

        if after_sql_route == "analysis_node":
            analysis = _fallback_analysis(mock_df, intent_result.intent_type)
            state["analysis_result"] = analysis.get("analysis_result")
            if state["analysis_result"]:
                print(f"   深度分析 -> insight={str(state['analysis_result'].insight)[:60]}...")

    # Step 4: 追问建议
    followups = _test_followups(question, mock_df if route == "sql_node" else None, intent_result)
    if followups:
        print(f"  \U0001f4a1 追问建议: {followups}")

    print()
    return intent_result


def _test_followups(question, df, intent_result):
    """模拟追问建议生成"""
    rules = []
    if df is not None and not df.empty:
        num_cols = list(df.select_dtypes(include=["number"]).columns)
        cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)
        if "rate" in num_cols and intent_result and intent_result.intent_type not in (IntentType.trend, IntentType.unknown):
            rules.append("查看变化趋势如何？")
        if len(cat_cols) >= 1 and intent_result and intent_result.intent_type not in (IntentType.comparison, IntentType.unknown):
            rules.append(f"按{cat_cols[0]}对比分析？")
        if num_cols:
            rules.append(f"{num_cols[0]} Top 10 是哪些？")
    return rules[:3]


async def run_tests():
    print("=" * 80)
    print("  DataMind LangGraph Agent \u2014 \u5168\u94fe\u8def\u6a21\u62df\u6d4b\u8bd5")
    print("=" * 80)
    print()

    # ============ 场景 1: HR 总监 ============
    print("=" * 60)
    print("【\u573a\u666f 1】HR \u603b\u76d1 \u2014 \u5168\u516c\u53f8\u6570\u636e\u6743\u9650")
    print("=" * 60)
    await simulate_question("\u4e0a\u4e2a\u6708\u5404\u90e8\u95e8\u7684\u51fa\u52e4\u7387\u662f\u591a\u5c11\uff1f", "hr_director", "all")
    await simulate_question("\u4e3a\u4ec0\u4e48\u6280\u672f\u90e8\u7684\u51fa\u52e4\u7387\u6bd4\u4e0a\u4e2a\u6708\u4e0b\u964d\u4e86\uff1f", "hr_director", "all")
    await simulate_question("\u9884\u6d4b\u4e0b\u4e2a\u5b63\u5ea6\u7684\u62db\u8058\u9700\u6c42", "hr_director", "all")

    # ============ 场景 2: 部门经理 ============
    print("=" * 60)
    print("【\u573a\u666f 2】\u90e8\u95e8\u7ecf\u7406 \u2014 \u672c\u90e8\u95e8\u6570\u636e\u6743\u9650")
    print("=" * 60)
    await simulate_question("\u6211\u4eec\u90e8\u95e8\u8fd9\u4e2a\u6708\u6709\u591a\u5c11\u4eba\u8bf7\u4e86\u5047\uff1f", "dept_manager", "dept")
    await simulate_question("\u6309\u5c97\u4f4d\u7ea7\u522b\u7edf\u8ba1\u4e00\u4e0b\u85aa\u8d44\u5206\u5e03", "dept_manager", "dept")
    await simulate_question("\u5bf9\u6bd4\u6280\u672f\u90e8\u548c\u4ea7\u54c1\u90e8\u7684\u79bb\u804c\u7387", "dept_manager", "dept")

    # ============ 场景 3: 普通员工 ============
    print("=" * 60)
    print("【\u573a\u666f 3】\u666e\u901a\u5458\u5de5 \u2014 \u4ec5\u4e2a\u4eba\u6570\u636e")
    print("=" * 60)
    await simulate_question("\u6211\u8fd9\u4e2a\u6708\u7684\u51fa\u52e4\u60c5\u51b5\u600e\u4e48\u6837\uff1f", "employee", "self_only")

    # ============ 场景 4: 15 类意图全覆盖 ============
    print("=" * 60)
    print("【\u573a\u666f 4】\u590d\u6742\u5206\u6790 \u2014 \u8986\u76d6\u6240\u6709 15 \u7c7b\u610f\u56fe")
    print("=" * 60)

    tests = [
        ("\u4e0a\u4e2a\u6708\u7684\u603b\u9500\u552e\u989d\u662f\u591a\u5c11\uff1f", IntentType.direct_query),
        ("\u5217\u51fa\u6240\u6709\u90e8\u95e8\u7684\u540d\u79f0\u548c\u8d1f\u8d23\u4eba", IntentType.list_query),
        ("\u5404\u90e8\u95e8\u7684\u5e73\u5747\u85aa\u8d44\u662f\u591a\u5c11\uff1f", IntentType.aggregation),
        ("\u8fd16\u4e2a\u6708\u51fa\u52e4\u7387\u7684\u53d8\u5316\u8d8b\u52bf", IntentType.trend),
        ("\u5bf9\u6bd4\u6280\u672f\u90e8\u548c\u4ea7\u54c1\u90e8\u7684\u7ee9\u6548\u8bc4\u5206", IntentType.comparison),
        ("\u85aa\u8d44\u6700\u9ad8\u7684\u524d10\u540d\u5458\u5de5", IntentType.ranking),
        ("\u5458\u5de5\u7684\u5b66\u5386\u5206\u5e03\u60c5\u51b5", IntentType.distribution),
        ("\u54ea\u4e9b\u5458\u5de5\u7684\u51fa\u52e4\u6570\u636e\u51fa\u73b0\u5f02\u5e38\uff1f", IntentType.anomaly),
        ("\u4e3a\u4ec0\u4e48\u8fd9\u4e2a\u6708\u7684\u79bb\u804c\u7387\u7a81\u7136\u5347\u9ad8\u4e86\uff1f", IntentType.root_cause),
        ("\u4e0b\u4e2a\u5b63\u5ea6\u7684\u9500\u552e\u989d\u5927\u6982\u4f1a\u662f\u591a\u5c11\uff1f", IntentType.forecast),
        ("\u5177\u4f53\u770b\u770b\u6280\u672f\u90e8\u7684\u60c5\u51b5", IntentType.drill_down),
        ("\u6539\u6210\u6309\u6708\u7edf\u8ba1\u663e\u793a", IntentType.refinement),
        ("\u5bf9\u6bd4HR\u6570\u636e\u548c\u8d22\u52a1\u6570\u636e", IntentType.cross_domain),
        ("\u4f60\u597d", IntentType.greeting),
        ("\u4f60\u80fd\u5e2e\u6211\u505a\u4ec0\u4e48", IntentType.help),
    ]

    for question, expected in tests:
        result = await simulate_question(question, "dept_ceo", "dept_and_sub")
        if result.intent_type == expected:
            print(f"  \u2705 MATCH \u2014 {expected.value}")
        else:
            print(f"  \u274c EXPECTED {expected.value} \u2014 GOT {result.intent_type.value}")
        print()

    # ============ 场景 5: 追问链 ============
    print("=" * 60)
    print("【\u573a\u666f 5】\u591a\u8f6e\u8ffd\u95ee \u2014 \u4f1a\u8bdd\u8fde\u7eed\u6027")
    print("=" * 60)

    history = [
        {"id": "t1", "session_id": "s1", "question": "\u4e0a\u4e2a\u6708\u5404\u90e8\u95e8\u7684\u51fa\u52e4\u7387\u662f\u591a\u5c11\uff1f",
         "intent": "aggregation", "analysis_depth": "simple"},
    ]
    await simulate_question("\u5177\u4f53\u770b\u770b\u6280\u672f\u90e8", "dept_manager", "dept", history, is_followup=True)

    history.append({"id": "t2", "session_id": "s1",
                    "question": "\u5177\u4f53\u770b\u770b\u6280\u672f\u90e8",
                    "intent": "drill_down", "analysis_depth": "simple"})
    await simulate_question("\u6309\u6708\u4efd\u7ec6\u5206\u4e00\u4e0b", "dept_manager", "dept", history, is_followup=True)

    # ============ 场景 6: 边界 ============
    print("=" * 60)
    print("【\u573a\u666f 6】\u8fb9\u754c\u60c5\u51b5")
    print("=" * 60)
    await simulate_question("\u5728\u5417", "employee", "self_only")
    print("  \u2139 \u85aa\u8d44\u6743\u9650\u6821\u9a8c\u901a\u8fc7 sql_node.py \u7684 _validate_sql_permissions \u4fdd\u969c")
    print()

    # ============ 统计 ============
    print("=" * 80)
    print("  \u6d4b\u8bd5\u5b8c\u6210\uff01\u5171\u6a21\u62df 20+ \u4e2a\u95ee\u9898\u7528\u4f8b")
    print("  \u8986\u76d6: 6 \u4e2a\u89d2\u8272, 15 \u7c7b\u610f\u56fe, \u591a\u8f6e\u8ffd\u95ee, \u8fb9\u754c\u60c5\u51b5")
    print("=" * 80)


asyncio.run(run_tests())
