import os

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

with open("app/core/query_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the FIRST occurrence of isinstance(val, list) - that's in _build_where
# The SECOND is in the duplicate _build_where (the one with RLS mixin)
# We need to fix BOTH

# Pattern for the FIRST _build_where (simple version)
target1 = """            if isinstance(val, str):
                conditions.append("\\"" + col + "\\" " + op + " '" + str(val) + "'")
            elif isinstance(val, list):
                vals_str = ", ".join("'" + str(v) + "'" for v in val)
                conditions.append("\\"" + col + "\\" " + op + " (" + vals_str + ")")"""

replacement1 = """            if isinstance(val, str):
                conditions.append("\\"" + col + "\\" " + op + " '" + str(val) + "'")
            elif isinstance(val, list):
                if op.upper() == "BETWEEN":
                    conditions.append("\\"" + col + "\\" BETWEEN '" + str(val[0]) + "' AND '" + str(val[1]) + "'")
                else:
                    vals_str = ", ".join("'" + str(v) + "'" for v in val)
                    conditions.append("\\"" + col + "\\" " + op + " (" + vals_str + ")")"""

print(f"Target1 found: {target1 in content}")

content = content.replace(target1, replacement1)

# Find the SECOND _build_where (the one with RLS mixin, uses user_conds)
target2 = """            if isinstance(val, str):
                user_conds.append(chr(34) + col + chr(34) + " " + op + " '" + str(val) + "'")
            elif isinstance(val, list):
                vs = ", ".join("'" + str(v) + "'" for v in val)
                user_conds.append(chr(34) + col + chr(34) + " " + op + " (" + vs + ")")"""

replacement2 = """            if isinstance(val, str):
                user_conds.append(chr(34) + col + chr(34) + " " + op + " '" + str(val) + "'")
            elif isinstance(val, list):
                if op.upper() == "BETWEEN":
                    user_conds.append(chr(34) + col + chr(34) + " BETWEEN '" + str(val[0]) + "' AND '" + str(val[1]) + "'")
                else:
                    vs = ", ".join("'" + str(v) + "'" for v in val)
                    user_conds.append(chr(34) + col + chr(34) + " " + op + " (" + vs + ")")"""

print(f"Target2 found: {target2 in content}")

content = content.replace(target2, replacement2)

with open("app/core/query_engine.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done - both BETWEEN blocks fixed")
