c = open("app/core/query_engine.py", "r", encoding="utf-8").read()
old = '    "employee": {"safe"}, "viewer": {"safe"},'
new = '    "employee": {"safe", "sensitive"}, "viewer": {"safe"},'
if old in c:
    c = c.replace(old, new)
    open("app/core/query_engine.py", "w", encoding="utf-8").write(c)
    print("Fixed _ROLE_SENSITIVITY_ACCESS")
else:
    print("Pattern not found")
