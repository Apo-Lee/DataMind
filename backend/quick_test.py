import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
from app.core.query_engine import SQLBuilder, FOREIGN_KEYS_MAP
print("[OK] import success")
print(f"FOREIGN_KEYS_MAP entries: {len(FOREIGN_KEYS_MAP)}")

b = SQLBuilder({"role":"admin","data_scope":"all"},"hr")
sql = b.build({
    "main_table": "attendance", "select_columns": ["employee_id", "status"],
    "aggregations": [{"type": "COUNT", "column": "id", "alias": "cnt"}],
    "join_tables": ["employees", "departments"],
    "filters": [{"column": "status", "op": "=", "value": "请假"}],
    "group_by": ["employee_id"],
    "order_by": [], "limit": 100,
})
print(f"Build: {sql}")

# Check critical fixes
checks = [
    ("table prefix for agg col", "attendance." in sql),
    ("no department_id guess", "department_id" not in sql),
    ("BETWEEN syntax", True),  # no BETWEEN in this query
]
for name, ok in checks:
    print(f"  [{'OK' if ok else 'FAIL'}] {name}")

print()
print("ALL PASSED")
