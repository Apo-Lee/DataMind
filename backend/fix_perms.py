import os

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

with open("app/core/query_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: dept_ceo permission - 添加 sensitive
old_perm = '''    "dept_ceo": {"safe"},  # 默认不能查看敏感字段'''
new_perm = '''    "dept_ceo": {"safe", "sensitive"},  # V3: 提升到 sensitive'''
content = content.replace(old_perm, new_perm)

# Also fix dept_manager and sales_manager
old_perm2 = '''    "dept_manager": {"safe"},
    "sales_manager": {"safe"},'''
new_perm2 = '''    "dept_manager": {"safe", "sensitive"},  # V3: 提升到 sensitive
    "sales_manager": {"safe", "sensitive"},  # V3: 提升到 sensitive'''
content = content.replace(old_perm2, new_perm2)

with open("app/core/query_engine.py", "w", encoding="utf-8") as f:
    f.write(content)

print("OK - permissions updated")
