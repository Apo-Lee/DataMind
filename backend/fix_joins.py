import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

with open("app/core/query_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# === Fix A: SQLBuilder 增加 table-aware 构建能力 ===
# _build_select 中聚合列加表名前缀（当有 JOIN 时）
# _build_joins 中只使用 FOREIGN_KEYS_MAP 映射（不猜列名）

# Fix A1: _build_select 中 COUNT("id") -> COUNT("main_table"."id") 当有 JOIN 时
old_select = """            if agg_col:
                col_level = table_sens.get(agg_col, "safe")
                if col_level not in self.max_level:
                    parts.append("0 AS \\"" + alias + "\\"")
                else:
                    parts.append(agg_type + "(\\"" + agg_col + "\\") AS \\"" + alias + "\\"")"""

new_select = """            if agg_col:
                col_level = table_sens.get(agg_col, "safe")
                if col_level not in self.max_level:
                    parts.append("0 AS \\"" + alias + "\\"")
                else:
                    if has_joins:
                        parts.append(agg_type + "(\\"" + main_table + "\\".\\"" + agg_col + "\\") AS \\"" + alias + "\\"")
                    else:
                        parts.append(agg_type + "(\\"" + agg_col + "\\") AS \\"" + alias + "\\"")"""

if old_select in content:
    content = content.replace(old_select, new_select)
    print("[OK] Fix A1: agg columns prefixed with table name when joins exist")
else:
    print("[WARN] Fix A1: pattern not found!")

# Fix A2: _build_joins 中只使用 FOREIGN_KEYS_MAP，去掉回退猜列名
old_join_fallback = """            elif jt in table_schema:
                # 探讨：找不到外键时跳过 JOIN
                pass
            else:
                fk_col = jt.rstrip("s") + "_id"
                joins.append("LEFT JOIN \\"" + jt + "\\" ON \\"" + jt + "\\".id = \\"" + intent.get("main_table", "") + "\\"." + fk_col)"""

# 把这个回退逻辑去掉，只保留 FOREIGN_KEYS_MAP 匹配
new_join_clean = """            # V3: 只使用已知外键映射，不猜列名
            #（猜列名会导致 attendence.department_id 这类错误）
            if key not in FOREIGN_KEYS_MAP:
                continue"""

if old_join_fallback in content:
    content = content.replace(old_join_fallback, new_join_clean)
    print("[OK] Fix A2: _build_joins uses FOREIGN_KEYS_MAP only, no fallback guessing")
else:
    print("[WARN] Fix A2: fallback pattern not found, checking current _build_joins...")
    # Show current _build_joins
    idx = content.find("def _build_joins")
    if idx >= 0:
        end_idx = content.find("def _build_where", idx)
        print(content[idx:end_idx])
    else:
        print("_build_joins not found!")

# Fix A3: 多表 SELECT 列也加前缀
# _build_select 开头的 has_joins 判断
# 还需要把 select_columns 的部分也加表名前缀——这个在 V3 中已经改了，但改在第一个版本
# 检查当前版本
old_select_cols = """        # 显式 select_columns
        for col in intent.get("select_columns", []):
            if table_sens.get(col, "safe") not in self.max_level:
                continue
            parts.append("\\"" + col + "\\"")"""

new_select_cols = """        # 显式 select_columns（多表时加表名前缀）
        for col in intent.get("select_columns", []):
            if table_sens.get(col, "safe") not in self.max_level:
                continue
            if has_joins:
                parts.append("\\"" + main_table + "\\".\\"" + col + "\\"")
            else:
                parts.append("\\"" + col + "\\"")"""

if old_select_cols in content:
    content = content.replace(old_select_cols, new_select_cols)
    print("[OK] Fix A3: select_columns prefixed with table name when joins exist")
else:
    print("[WARN] Fix A3: pattern not found, checking...")
    idx = content.find('intent.get("select_columns"')
    if idx >= 0:
        print(f"  Current: ...{content[idx:idx+180]}...")


with open("app/core/query_engine.py", "w", encoding="utf-8") as f:
    f.write(content)

print("\nAll fixes applied!")
