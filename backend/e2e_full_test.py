"""DataMind Agent 全链路测试（不依赖外部 LLM API）
使用真实 SQLite 数据库 + mock LLM 返回 + 真实用户权限
"""
import os, sys, json, asyncio
os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
sys.path.insert(0, ".")

from sqlalchemy import select, text
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.models.user import User
from app.models.datasource import DataSource
from app.core.permissions import get_agent_with_rls
from app.core.query_engine import safe_query
from app.agents.base import DataSourceAgent

# ============================================================
# 测试用户配置
# ============================================================
USERS = {
    "dept_ceo": {
        "username": "emp1", "display": "张伟(技术总监)",
        "role": "dept_ceo", "data_scope": "dept",
        "dept_id": 1, "employee_id": 1,
        "expected": "可查本部门所有数据",
    },
    "dept_manager": {
        "username": "emp17", "display": "沈洁(部门经理)",
        "role": "dept_manager", "data_scope": "team",
        "dept_id": 102, "employee_id": 17,
        "expected": "可查本部门数据",
    },
    "employee": {
        "username": "emp2", "display": "孙明(普通员工)",
        "role": "employee", "data_scope": "self_only",
        "dept_id": 101, "employee_id": 2,
        "expected": "仅个人数据",
    },
    "admin": {
        "username": "admin", "display": "系统管理员",
        "role": "admin", "data_scope": "all",
        "dept_id": None, "employee_id": None,
        "expected": "全公司数据",
    },
}

# 真实 HR 数据库引擎（用于验证 SQL 可执行性）
hr_engine = create_engine("sqlite:///../demo_data/hr_demo.sqlite")

# ============================================================
# 模拟 LLM 意图（绕过 API 调用）
# ============================================================
MOCK_INTENTS = {
    "技术研发中心有多少员工": {
        "question_type": "count",
        "main_table": "employees",
        "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "id", "alias": "员工数量"}],
        "filters": [{"column": "dept_id", "op": "=", "value": 1}],
        "group_by": [],
        "order_by": [],
        "limit": 10,
    },
    "各部门的平均薪资是多少": {
        "question_type": "aggregation",
        "main_table": "employees",
        "join_tables": ["departments"],
        "select_columns": [],
        "aggregations": [{"type": "AVG", "column": "salary", "alias": "平均薪资"}],
        "filters": [],
        "group_by": ["dept_id"],
        "order_by": [],
        "limit": 100,
    },
    "员工的学历分布情况": {
        "question_type": "aggregation",
        "main_table": "employees",
        "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "id", "alias": "人数"}],
        "filters": [],
        "group_by": ["education"],
        "order_by": [],
        "limit": 100,
    },
    "上个月各部门的出勤率是多少": {
        "question_type": "aggregation",
        "main_table": "attendance",
        "join_tables": ["employees", "departments"],
        "select_columns": [],
        "aggregations": [
            {"type": "COUNT", "column": "id", "alias": "total_records"},
            {"type": "SUM", "column": None, "alias": "normal_count"},
        ],
        "filters": [{"column": "date", "op": "BETWEEN", "value": ["2026-01-01", "2026-01-31"]}],
        "group_by": ["dept_id"],
        "order_by": [],
        "limit": 100,
    },
    "绩效评分最高的前10名员工": {
        "question_type": "ranking",
        "main_table": "employees",
        "join_tables": [],
        "select_columns": ["name", "performance_score"],
        "aggregations": [],
        "filters": [],
        "group_by": [],
        "order_by": [{"column": "performance_score", "direction": "DESC"}],
        "limit": 10,
    },
    "本部门本月有多少人请假": {
        "question_type": "count",
        "main_table": "attendance",
        "join_tables": [],
        "select_columns": [],
        "aggregations": [{"type": "COUNT", "column": "employee_id", "alias": "leave_count"}],
        "filters": [{"column": "status", "op": "=", "value": "请假"}],
        "group_by": [],
        "order_by": [],
        "limit": 100,
    },
    "本月出勤情况": {
        "question_type": "list",
        "main_table": "attendance",
        "join_tables": [],
        "select_columns": ["employee_id", "date", "status"],
        "aggregations": [],
        "filters": [{"column": "date", "op": "BETWEEN", "value": ["2026-01-01", "2026-01-31"]}],
        "group_by": [],
        "order_by": [],
        "limit": 100,
    },
    "所有人的薪资是多少": {
        "question_type": "list",
        "main_table": "employees",
        "join_tables": [],
        "select_columns": ["name", "salary"],
        "aggregations": [],
        "filters": [],
        "group_by": [],
        "order_by": [],
        "limit": 100,
    },
    "全公司的出勤率": {
        "question_type": "aggregation",
        "main_table": "attendance",
        "join_tables": [],
        "select_columns": [],
        "aggregations": [
            {"type": "COUNT", "column": "id", "alias": "total"},
            {"type": "SUM", "column": None, "alias": "normal_count"},
        ],
        "filters": [],
        "group_by": [],
        "order_by": [],
        "limit": 100,
    },
}

# 将 mock intent 注入到 safe_query 中
original_parse = None


def inject_mock_intent(mock_intents):
    """替换 parse_query_intent 为 mock 版本"""
    import app.core.query_engine as qe
    global original_parse
    original_parse = qe.parse_query_intent
    
    async def mock_parse(question, agent):
        if question in mock_intents:
            return mock_intents[question]
        # fallback: 尝试简化匹配
        for key, val in mock_intents.items():
            if key in question or question in key:
                return val
        # 返回默认
        return {
            "question_type": "list",
            "main_table": "employees",
            "join_tables": [],
            "select_columns": ["name"],
            "aggregations": [],
            "filters": [],
            "group_by": [],
            "order_by": [],
            "limit": 10,
        }
    
    qe.parse_query_intent = mock_parse


def restore_original_parse():
    if original_parse:
        import app.core.query_engine as qe
        qe.parse_query_intent = original_parse


# ============================================================
# SQL 验证：在真实 SQLite 上执行并检查结果
# ============================================================
def verify_sql(sql: str) -> dict:
    """在真实 HR SQLite 上执行 SQL 并验证"""
    if not sql:
        return {"ok": False, "error": "SQL为空", "rows": 0}
    
    sql_upper = sql.upper()
    errors = []
    warnings = []
    
    # 安全检查
    if not sql_upper.strip().startswith("SELECT"):
        errors.append("不是SELECT语句")
    
    for kw in ["INSERT","UPDATE","DELETE","DROP","ALTER","TRUNCATE","CREATE","GRANT","REVOKE"]:
        if kw in sql_upper:
            errors.append(f"包含危险操作: {kw}")
    
    if "LIMIT" not in sql_upper:
        warnings.append("没有LIMIT限制")
    
    # 列存在性检查
    if "departments" in sql.lower():
        for bad_col in ['"dept_id"', '"department_id"']:
            if bad_col in sql:
                errors.append(f"departments表没有{bad_col}列!")
    
    # 实际执行
    try:
        with hr_engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            return {
                "ok": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "rows": len(rows),
                "columns": list(result.keys()) if rows else [],
                "sample": [dict(zip(result.keys(), r)) for r in rows[:3]] if rows else [],
            }
    except Exception as e:
        errors.append(f"SQL执行错误: {str(e)[:200]}")
        return {"ok": False, "errors": errors, "warnings": warnings, "rows": 0, "columns": []}


# ============================================================
# 主测试
# ============================================================
async def run():
    print("=" * 80)
    print("DataMind Agent 全链路测试（真实数据库 + Mock LLM + 真实权限）")
    print("=" * 80)
    
    # 注入 mock intent
    inject_mock_intent(MOCK_INTENTS)
    
    # 连接系统数据库
    engine = create_async_engine(settings.database_url)
    session = async_sessionmaker(engine, class_=AsyncSession)()
    
    # 获取 HR 数据源
    ds_result = await session.execute(
        select(DataSource).where(DataSource.business_tag == "hr", DataSource.is_active == True)
    )
    hr_ds = ds_result.scalar_one_or_none()
    print(f"\n数据源: {hr_ds.name} (id={hr_ds.id[:12]}...)")
    
    # ============================================================
    # 测试用例
    # ============================================================
    test_cases = [
        # (用户, 问题, 预期行为)
        
        # 部门CEO - 简单查询
        ("dept_ceo", "技术研发中心有多少员工", "通过"),
        ("dept_ceo", "各部门的平均薪资是多少", "通过"),
        ("dept_ceo", "员工的学历分布情况", "通过"),
        ("dept_ceo", "绩效评分最高的前10名员工", "通过"),
        ("dept_ceo", "上个月各部门的出勤率是多少", "通过"),
        
        # 部门经理 - 本部门查询
        ("dept_manager", "本部门本月有多少人请假", "通过"),
        
        # 普通员工 - 个人数据
        ("employee", "本月出勤情况", "通过"),
        
        # 权限拒绝
        ("employee", "所有人的薪资是多少", "拒绝"),
        ("employee", "全公司的出勤率", "拒绝"),
    ]
    
    all_results = []
    
    for user_key, question, expected in test_cases:
        user_info = USERS[user_key]
        
        print(f"\n{'='*60}")
        print(f"用户: {user_info['display']}  ({user_info['role']})")
        print(f"权限: {user_info['expected']}")
        print(f"问题: {question}")
        print(f"预期: {expected}")
        
        # 构造用户对象
        class MockUser:
            id = f"mock-{user_key}"
            role = user_info["role"]
            data_scope = user_info["data_scope"]
            employee_id = user_info["employee_id"]
            dept_id = user_info["dept_id"]
            dept_name = ""
        
        user = MockUser()
        
        try:
            # 获取 Agent 并注入权限
            agent, _ = await get_agent_with_rls(user, hr_ds.id, session)
            agent._user_role = user_info["role"]
            agent._user_data_scope = user_info["data_scope"]
            agent._user_id = user.id
            agent._user_employee_id = user_info["employee_id"]
            agent._user_dept_id = user_info["dept_id"]
            agent._user_dept_name = user_info.get("dept_name", "")
            
            # 执行查询
            result = await safe_query(question, agent, {
                "role": user_info["role"],
                "data_scope": user_info["data_scope"],
                "employee_id": user_info["employee_id"],
                "dept_id": user_info["dept_id"],
            })
            
            if result.get("rejected"):
                err = result.get("error", "")
                print(f"  结果: ❌ 拒绝 - {err}")
                all_results.append((user_key, question, "REJECTED", err, ""))
                if expected == "通过":
                    print(f"  评价: ✗ 预期通过但被拒绝!")
            else:
                sql = result.get("sql", "")
                verification = verify_sql(sql)
                
                if verification["ok"]:
                    rows_display = verification["rows"]
                    cols = verification["columns"]
                    sample = verification.get("sample", [])
                    print(f"  结果: ✅ SQL可执行 ({rows_display}行, 列={cols})")
                    print(f"  SQL: {sql[:200]}")
                    if sample:
                        print(f"  数据样例: {json.dumps(sample, ensure_ascii=False)[:150]}")
                    all_results.append((user_key, question, f"OK({rows_display}行)", sql[:100], ""))
                    if expected == "拒绝":
                        print(f"  评价: ✗ 预期拒绝但通过了!")
                else:
                    errors = "; ".join(verification["errors"])
                    print(f"  结果: ❌ SQL错误 - {errors}")
                    print(f"  SQL: {sql[:200]}")
                    all_results.append((user_key, question, f"SQL_ERROR", "", errors))
                    if expected == "拒绝":
                        print(f"  评价: ℹ 预期拒绝，但SQL错误是意外")
            
            if verification and verification.get("warnings"):
                for w in verification["warnings"]:
                    print(f"  警告: {w}")
                    
        except Exception as e:
            print(f"  结果: ❌ 异常 - {e}")
            all_results.append((user_key, question, "EXCEPTION", "", str(e)[:100]))
    
    # 汇总
    print("\n" + "=" * 80)
    print("最终测试汇总")
    print("=" * 80)
    
    ok = sum(1 for r in all_results if r[2].startswith("OK"))
    rejected = sum(1 for r in all_results if r[2] == "REJECTED")
    failed = sum(1 for r in all_results if r[2] in ("SQL_ERROR", "EXCEPTION"))
    total = len(all_results)
    
    print(f"\n总用例: {total}")
    print(f"SQL可执行: {ok}")
    print(f"权限拒绝(预期): {rejected}")
    print(f"失败: {failed}")
    print(f"SQL可执行成功率: {ok}/{total} = {ok/total*100:.0f}%" if total > 0 else "")
    
    print(f"\n详细结果:")
    for r in all_results:
        status_icon = "✅" if r[2].startswith("OK") else "❌" if r[2] in ("SQL_ERROR","EXCEPTION") else "⛔"
        sql_short = r[3][:80] if r[3] else ""
        print(f"  {status_icon} [{r[0]}] {r[1][:20]:20s} -> {r[2]:15s}  {sql_short}")
    
    # 恢复原始 parse
    restore_original_parse()
    await session.close()
    await engine.dispose()


asyncio.run(run())
