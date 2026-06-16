c = open("app/core/query_engine.py", "r", encoding="utf-8").read()
old = "\"salary\": \"highly_sensitive\""
new = "\"salary\": \"sensitive\""
count = c.count(old)
if count > 0:
    c = c.replace(old, new)
    open("app/core/query_engine.py", "w", encoding="utf-8").write(c)
    print(f"Changed {count} occurrence(s) of salary: highly_sensitive -> sensitive")
else:
    print("Pattern not found")
    # debug: find any salary line
    for i, line in enumerate(c.split(chr(10))):
        if "salary" in line.lower():
            print(f"Line {i}: {line[:100]}")
