"""深入测试：对每条生成的 SQL 在真实 SQLite 上执行并验证正确性"""
import asyncio, os, sys
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

hr_engine = create_engine("sqlite:///../demo_data/hr_demo.sqlite")


def get_role_str(role_val):
    """统一获取角色字符串"""
    return role_val.value if hasattr(role_val, "value") else role_val


def verify_sql_on_real_db(sql):
    """在真实 SQLite 上执行 SQL 并验证"""
    if not sql:
        return {"valid": False, "errors": ["SQL 为空"], "rows": 0}
    
    sql_upper = sql.upper()
    sql_lower = sql.lower()
    errors = []
    warnings = []
    
    # 安全检查
    if not sql_upper.strip().startswith("SELECT"):
        errors.append("不是 SELECT 语句")
    
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    for kw in dangerous:
        if kw in sql_upper:
            errors.append(f"包含危险操作: {kw}")
    
    if "LIMIT" not in sql_upper:
        warnings.append("没有 LIMIT 限制")
    
    # 列存在性检查 — departments 表没有 dept_id
    if "departments" in sql_lower:
        has_dept_dot = '"dept_id"' in sql or '"department_id"' in sql
        has_where = "WHERE" in sql_upper
        if has_dept_dot:
            errors.append("departments表没有dept_id/department_id列！只有: id, name, parent_dept_id, manager_name, budget, location")
        if "GROUP BY" in sql_upper and "departments" in sql_lower and "dept_id" not in sql_lower:
            warnings.append("跨表查询可能缺少正确的JOIN条件")
    
    # 出勤状态值检查
    if "attendance" in sql_lower and "status" in sql_lower:
        if "'正常'" in sql or "'present'" in sql:
            errors.append("出勤状态值错误！数据库中使用的是中文'出勤'，不是'正常'或'present'")
        # 正确的值应该是"出勤"
        if "'出勤'" in sql:
            pass  # 正确
    
    # 实际执行
    try:
        with hr_engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            row_count = len(rows)
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "rows": row_count,
                "columns": list(result.keys()) if rows else [],
            }
    except Exception as e:
        errors.append(f"SQL执行错误: {e}")
        return {"valid": False, "errors": errors, "warnings": warnings, "rows": 0, "columns": []}


TEST_CASES = [
    # (test_id, username, role_str, data_scope, ds_tag, question)
    # --- 简单查询 ---
    ("S1",  "emp1", "dept_ceo",    "team",      "hr",  "技术研发中心有多少员工"),
    ("S2",  "emp1", "dept_ceo",    "team",      "hr",  "列出所有部门的名称"),
    ("S3",  "emp1", "dept_ceo",    "team",      "hr",  "人力资源部的预算是多少"),
    
    # --- 聚合统计 ---
    ("A1",  "emp1", "dept_ceo",    "team",      "hr",  "各部门的平均薪资是多少"),
    ("A2",  "emp1", "dept_ceo",    "team",      "hr",  "员工的学历分布情况"),
    ("A3",  "emp1", "dept_ceo",    "team",      "hr",  "每个部门的薪资总额排行"),
    
    # --- 出勤率 ---
    ("AT1", "emp1", "dept_ceo",    "team",      "hr",  "上个月各部门的出勤率是多少"),
    ("AT2", "emp1", "dept_ceo",    "team",      "hr",  "近6个月出勤率变化趋势"),
    ("AT3", "emp17","dept_manager", "team",      "hr",  "我们部门本月有多少人请假"),
    
    # --- 对比 & 排行 ---
    ("C1",  "emp1", "dept_ceo",    "team",      "hr",  "对比技术研发中心和市场营销部的平均绩效评分"),
    ("R1",  "emp1", "dept_ceo",    "team",      "hr",  "绩效评分最高的前10名员工"),
    
    # --- 权限边界 ---
    ("P1",  "emp2", "employee",    "self_only", "hr",  "所有人的薪资是多少"),
    ("P2",  "emp2", "employee",    "self_only", "hr",  "全公司的出勤率"),
    
    # --- CRM 场景 ---
    ("CR1", "emp1", "dept_ceo",    "team",      "crm", "上个月的销售总额是多少"),
    ("CR2", "emp1", "dept_ceo",    "team",      "crm", "各行业的客户数量分布"),
    ("CR3", "emp1", "dept_ceo",    "team",      "crm", "赢单率最高的销售团队是哪个"),
]


async def run():
    print("=" * 80)
    print("DataMind Agent SQL 深入验证测试")
    print("=" * 80)
    
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    db = async_session()
    
    results = []
    
    try:
        for test_id, username, role_str, data_scope, ds_tag, question in TEST_CASES:
            print(f"\n[{test_id}] ({role_str}) {question}")
            
            # 获取用户和数据源
            u_result = await db.execute(select(User).where(User.username == username))
            user = u_result.scalar_one_or_none()
            
            ds_result = await db.execute(
                select(DataSource).where(DataSource.business_tag == ds_tag, DataSource.is_active == True)
            )
            ds = ds_result.scalar_one_or_none()
            
            if not user or not ds:
                print(f"  SKIP")
                continue
            
            try:
                agent, _ = await get_agent_with_rls(user, ds.id, db)
                agent._user_role = role_str
                agent._user_data_scope = data_scope
                agent._user_id = user.id
                agent._user_employee_id = user.employee_id
                agent._user_dept_id = user.dept_id
                
                user_info = {
                    "role": agent._user_role,
                    "data_scope": agent._user_data_scope,
                    "employee_id": agent._user_employee_id,
                    "dept_id": agent._user_dept_id,
                }
                
                query_result = await safe_query(question, agent, user_info)
                
                if query_result.get("rejected"):
                    if test_id.startswith("P"):
                        print(f"  [PASS] 已正确拒绝: {query_result.get('error','')}")
                        results.append((test_id, "PASS", query_result.get('error','')))
                    else:
                        print(f"  [FAIL] 不应被拒绝: {query_result.get('error','')}")
                        results.append((test_id, "FAIL", query_result.get('error','')))
                    continue
                
                sql = query_result.get("sql", "")
                if not sql:
                    print(f"  [FAIL] 未生成SQL")
                    results.append((test_id, "FAIL", "无SQL"))
                    continue
                
                verification = verify_sql_on_real_db(sql)
                
                if verification["valid"]:
                    status = "PASS"
                    msg = f"{verification['rows']}行 列={verification['columns']}"
                else:
                    status = "FAIL"
                    msg = f"错误: {'; '.join(verification['errors'])}"
                
                print(f"  [{status}] {msg}")
                if verification["warnings"]:
                    for w in verification["warnings"]:
                        print(f"  [WARN] {w}")
                print(f"  SQL: {sql[:200]}")
                
                results.append((test_id, status, msg, sql[:200]))
                
            except Exception as e:
                print(f"  [ERROR] {e}")
                results.append((test_id, "ERROR", str(e)))
    
    finally:
        await db.close()
        await engine.dispose()
    
    # 汇总
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    passed = sum(1 for r in results if r[1] == "PASS")
    total = len(results)
    print(f"\n总用例: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total-passed}")
    print(f"通过率: {passed/total*100:.0f}%")
    print()
    
    for r in results:
        if r[1] == "FAIL":
            print(f"  [FAIL] {r[0]}: {r[2]}")
    
    print("\n" + "=" * 80)


asyncio.run(run())
