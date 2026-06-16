import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

with open("app/core/query_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the right place to insert FOREIGN_KEYS_MAP — before class SQLBuilder
target = "class SQLBuilder:"
insert = """

# V3: Known foreign key mapping (main_table, join_table) -> (main_fk_col, join_pk_col)
FOREIGN_KEYS_MAP = {
    ("employees", "departments"): ("dept_id", "id"),
    ("attendance", "employees"): ("employee_id", "id"),
    ("deals", "customers"): ("customer_id", "id"),
    ("customers", "departments"): ("owner_dept_id", "id"),
    ("projects", "departments"): ("dept_id", "id"),
    ("purchase_orders", "departments"): ("dept_id", "id"),
    ("resources", "projects"): ("project_id", "id"),
}
"""

if target in content:
    content = content.replace(target, insert + "\n" + target)
    with open("app/core/query_engine.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] FOREIGN_KEYS_MAP definition added before SQLBuilder")
else:
    print("[FAIL] Could not find class SQLBuilder")
