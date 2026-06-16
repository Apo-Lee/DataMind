import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
from app.orchestrator.errors import *

# Permission
e1 = make_friendly_permission_error("无权查询列 salary（级别: highly_sensitive）")
print(f"Permission: {e1.message}")
print(f"  Suggestion: {e1.suggestion}")
print(f"  Followups: {e1.followups}")

e2 = make_friendly_permission_error("员工角色不能执行 SUM/AVG 聚合操作")
print(f"\nEmployee: {e2.message}")
print(f"  Suggestion: {e2.suggestion}")

# SQL error
e3 = classify_sql_error("sqlite3.OperationalError: no such column: dept_id")
print(f"\nSQL column: {e3.message}")
print(f"  Suggestion: {e3.suggestion}")

e4 = classify_sql_error("ambiguous column name: id")
print(f"\nAmbiguous: {e4.message}")
print(f"  Suggestion: {e4.suggestion}")

# Intent
e5 = make_friendly_intent_error("LLM API failed")
print(f"\nIntent: {e5.message}")
print(f"  Suggestion: {e5.suggestion}")

# Response format
resp = e1.to_user_response()
print(f"\nResponse report_markdown:")
print(resp["report_markdown"])
print(f"\nResponse followups: {resp['followups']}")
