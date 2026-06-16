# -*- coding: utf-8 -*-
"""Apply SQL query engine fixes"""
import re, os
os.chdir("E:/Python_Code_Project/DataMind/backend")

path = "app/core/query_engine.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Fix 1: BETWEEN merge
old = """        for f in intent.get("filters", []):
            col = f.get("column", "")
            op = f.get("op", "=")
            val = f.get("value", "")
            if isinstance(val, str):
                user_conds.append("\"" + col + "\" " + op + " '" + str(val) + "'")
            elif isinstance(val, list):
                if op.upper() == "BETWEEN":
                    user_conds.append("\"" + col + "\" BETWEEN '" + str(val[0]) + "' AND '" + str(val[1]) + "'")
                else:
                    vs = ", ".join("'" + str(v) + "'" for v in val)
                    user_conds.append("\"" + col + "\" " + op + " (" + vs + ")")
            else:
                user_conds.append("\"" + col + "\" " + op + " " + str(val))
        return " AND ".join(user_conds) if user_conds else """"