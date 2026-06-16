import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

# 读取当前 query_engine.py
with open("app/core/query_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# === Fix 1: _build_select 中聚合列 column=None 时用 COUNT(*) 而非 SUM(*) ===
old_agg_none = """            else:
                parts.append(agg_type + "(*) AS " + alias)"""

new_agg_none = """            else:
                if agg_type == "SUM":
                    parts.append("COUNT(*) AS " + alias)
                else:
                    parts.append(agg_type + "(*) AS " + alias)"""

if old_agg_none in content:
    content = content.replace(old_agg_none, new_agg_none)
    print("[OK] Fix 1: SUM(*) -> COUNT(*) when column is None")
else:
    print("[WARN] Fix 1: old_agg_none not found!")
    # Find the actual text
    idx = content.find('agg_type + "(*) AS "')
    if idx >= 0:
        print(f"  Found at {idx}: ...{content[idx-20:idx+50]}...")

# === Fix 2: _build_joins 中 departments JOIN 用 department_id 改为 dept_id ===
# 需要找到 _build_joins 中推断外键的逻辑
# 当前逻辑: fk_col = jt.rstrip("s") + "_id" → "departments".rstrip("s") = "department" + "_id" = "department_id"
# 改为使用 FOREIGN_KEYS 映射表

old_joins = """        for jt in intent.get("join_tables", []):
            # 根据命名约定推断外键
            fk_col = jt.rstrip("s") + "_id"
            joins.append("LEFT JOIN \\"" + jt + "\\" ON \\"" + jt + "\\".id = \\"" + intent.get("main_table", "") + "\\"." + fk_col)"""

new_joins = """        table_schema = getattr(self, '_table_schema', {})
        for jt in intent.get("join_tables", []):
            key = (intent.get("main_table", ""), jt)
            if key in FOREIGN_KEYS_MAP:
                fk_col, pk_col = FOREIGN_KEYS_MAP[key]
                joins.append("LEFT JOIN \\"" + jt + "\\" ON \\"" + jt + "\\".\\"" + pk_col + "\\" = \\"" + intent.get("main_table", "") + "\\".\\"" + fk_col + "\\"")
            elif jt in table_schema:
                # 探讨：找不到外键时跳过 JOIN
                pass
            else:
                fk_col = jt.rstrip("s") + "_id"
                joins.append("LEFT JOIN \\"" + jt + "\\" ON \\"" + jt + "\\".id = \\"" + intent.get("main_table", "") + "\\"." + fk_col)"""

if old_joins in content:
    content = content.replace(old_joins, new_joins)
    print("[OK] Fix 2: _build_joins uses FOREIGN_KEYS_MAP")
else:
    print("[WARN] Fix 2: old_joins not found!")
    idx = content.find("fk_col = jt.rstrip")
    if idx >= 0:
        print(f"  Found at {idx}: ...{content[idx:idx+120]}...")
        old = content[idx:idx+120]
        # Find the full line
        end = content.find("\n", idx)
        old_line = content[idx:end]
        print(f"  Line: {old_line}")

# === Fix 3: FOREIGN_KEYS_MAP 定义 ===
# 在 SQLBuilder 类前加入外键映射表
fk_map_def = """

# V3: 已知外键映射 (main_table, join_table) -> (main_fk_col, join_pk_col)
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

if "FOREIGN_KEYS_MAP" not in content:
    # 在 class SQLBuilder 前插入
    content = content.replace("class SQLBuilder:", fk_map_def + "\nclass SQLBuilder:")
    print("[OK] Fix 3: Added FOREIGN_KEYS_MAP")
else:
    print("[WARN] Fix 3: FOREIGN_KEYS_MAP already exists")

with open("app/core/query_engine.py", "w", encoding="utf-8") as f:
    f.write(content)

print("\nDone!")
