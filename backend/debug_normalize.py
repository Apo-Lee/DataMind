import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
import re

# 重新实现 normalize_sql_values 的逻辑
_STATUS_FIXES = [
    ("present", "出勤"),
    ("normal", "出勤"),
    ("absent", "缺勤"),
    ("leave", "请假"),
    ("late", "迟到"),
]

def normalize_value(sql, eng, chn):
    sql = re.sub(r"'" + re.escape(eng) + r"'", "'" + chn + "'", sql)
    sql = re.sub(r'"' + re.escape(eng) + r'"', "'" + chn + "'", sql)
    return sql

sql1 = "SELECT * FROM attendance WHERE status = 'normal'"
print(f"  Input: {repr(sql1)}")
n1 = sql1
for eng, chn in _STATUS_FIXES:
    n1 = normalize_value(n1, eng, chn)
print(f"  Output: {repr(n1)}")
print(f"  Expected: status = '出勤'")
print()

# 仔细看为什么会有 '' 出现
# 'present' -> '出勤' 发生在 'normal' 之前？
# 不对，上面没有反斜杠就是字面量
sql2 = "SELECT * FROM attendance WHERE status = 'present'"
print(f"  Input: {repr(sql2)}")
n2 = sql2
for eng, chn in _STATUS_FIXES:
    n2 = normalize_value(n2, eng, chn)
print(f"  Output: {repr(n2)}")
