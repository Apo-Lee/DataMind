import os, re

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

with open("app/core/query_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. 修改 _STATUS_FIXES：加入 normal
old_status = "('present', '出勤'), ('absent', '缺勤'),"
new_status = "('present', '出勤'), ('normal', '出勤'), ('absent', '缺勤'),"
content = content.replace(old_status, new_status)

# 2. 修改 normalize_sql_values：改用 re.sub
old_func = """def normalize_sql_values(sql: str) -> str:
    \"""自动修正 SQL 中常见的枚举值错误（英文 -> 中文）\"""
    for eng, chn in _STATUS_FIXES:
        sql = sql.replace(eng, "'" + chn + "'")
    return sql"""

new_func = """def normalize_sql_values(sql: str) -> str:
    \"""自动修正 SQL 中常见的枚举值错误（英文 -> 中文）\"""
    for eng, chn in _STATUS_FIXES:
        pat_eng = re.escape(eng)
        sql = re.sub("'" + "'" + "'" + " + pat_eng + " + "'" + "'" + "'" + ", " + "'" + "'" + "'" + " + chn + " + "'" + "'" + "'" + ", sql)
        sql = re.sub('" + "'" + "'" + '\"' + "'" + "'" + " + pat_eng + " + "'" + "'" + '\"' + "'" + "'" + ", " + "'" + "'" + "'" + " + chn + " + "'" + "'" + "'" + ", sql)
    return sql"""

# This is getting too complicated with escaping. Just do a simpler approach.
# Replace the entire function with a version that avoids nested quotes
new_func_simple = """def normalize_sql_values(sql: str) -> str:
    for eng, chn in _STATUS_FIXES:
        escaped = re.escape(eng)
        sql = re.sub("'" + escaped + "'", "'" + chn + "'", sql)
        sql = re.sub('"' + escaped + '"', "'" + chn + "'", sql)
    return sql"""

if old_func in content:
    content = content.replace(old_func, new_func_simple)
    with open("app/core/query_engine.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("OK - replaced function")
else:
    print("old_func not found!")
    # check what we have
    idx = content.find("def normalize_sql_values")
    if idx >= 0:
        end = content.find("\n\n", idx)
        print("Current content:")
        print(content[idx:end+2])
