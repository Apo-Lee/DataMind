import os, sys
sys.stdout.reconfigure(encoding="utf-8")
os.chdir("E:/Python_Code_Project/DataMind/backend")

print("=== Applying Agent fixes ===")

# FIX 1: state.py - routing logic
path = "app/orchestrator/state.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

old = 'if intent_result is None or intent_result.status != "success":\n        return "sql_node"'
new = 'if intent_result is None or intent_result.status != "success":\n        return "report_node"'
text = text.replace(old, new)

old = 'if sql_result is None or sql_result.status != "success":\n        return "report_node"\n\n    # \u5982\u679c\u610f\u56fe\u662f\u6df1\u5ea6\u5206\u6790\u4e14\u6570\u636e\u975e\u7a7a\n    if intent_result and intent_result.analysis_depth == "complex":\n        if sql_result.df is not None and not sql_result.df.empty:\n            return "analysis_node"'
new = 'if sql_result is None or sql_result.status != "success":\n        if intent_result and intent_result.analysis_depth == "complex":\n            return "analysis_node"\n        return "report_node"\n\n    # \u5982\u679c\u610f\u56fe\u662f\u6df1\u5ea6\u5206\u6790\n    if intent_result and intent_result.analysis_depth == "complex":\n        return "analysis_node"'
if old in text:
    text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("[OK] state.py routing fix applied")
else:
    print("[WARN] state.py: old code not found")
    # Debug
    idx = text.find("route_after_sql")
    if idx >= 0:
        print(text[idx:idx+800])

# FIX 2: intent_node.py - better greeting detection
path = "app/orchestrator/nodes/intent_node.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

old = 'greeting_patterns = ["\u4f60\u597d", "\u60a8\u597d", "hi", "hello", "hey", "\u5728\u5417", "\u5728\u4e0d\u5728"]\n    if question.strip() in greeting_patterns or question.strip().lower() in greeting_patterns:\n        return {'
new = 'greeting_patterns = ["\u4f60\u597d", "\u60a8\u597d", "hi", "hello", "hey", "\u5728\u5417", "\u5728\u4e0d\u5728"]\n    if question.strip() in greeting_patterns or question.strip().lower() in [g.lower() for g in greeting_patterns]:\n        return {'
text = text.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("[OK] intent_node.py greeting detection fixed")

# FIX 3: report_node.py - better followup suggestions
path = "app/orchestrator/nodes/report_node.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Edit lines 164-200 (the _generate_followups function)
new_lines = []
in_func = False
func_indent = "    "
for i, line in enumerate(lines):
    if 'async def _generate_followups' in line:
        in_func = True
        func_indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        # We'll skip the old function body and add new one at the end
        continue
    if in_func:
        stripped = line.strip()
        # End of function: empty line followed by a non-indented non-comment line
        if stripped and not line.startswith(" ") and not line.startswith("\t") and not stripped.startswith("#") and not stripped.startswith('"""'):
            if stripped.startswith("async ") or stripped.startswith("def ") or stripped == "":
                pass
            else:
                in_func = False
                new_lines.append(line)
                continue
        # Skip old function body lines
        continue
    new_lines.append(line)

# Add new function body after the last line
new_func_body = '''async def _generate_followups(question: str, df, intent_result: IntentResult | None) -> list[str]:
    """生成追问建议 - 基于实际数据动态生成"""
    rules: list[str] = []

    if df is not None and not df.empty:
        num_cols = list(df.select_dtypes(include=["number"]).columns)
        cat_cols = list(df.select_dtypes(include=["object", "str", "category"]).columns)

        # 规则1：有时间列但没做趋势
        time_keywords = ["date", "time", "month", "year", "day", "日期", "时间", "月", "年"]
        has_time = any(any(kw in str(c).lower() for kw in time_keywords) for c in df.columns)
        if has_time and intent_result and intent_result.intent_type not in (IntentType.trend, IntentType.unknown):
            rules.append("查看变化趋势如何？")

        # 规则2：有分类列可对比
        if len(cat_cols) >= 1 and intent_result and intent_result.intent_type not in (IntentType.comparison, IntentType.unknown):
            rules.append(f"对比不同{cat_cols[0]}的表现？")

        # 规则3：有数值列可排行
        if num_cols and intent_result and intent_result.intent_type not in (IntentType.ranking, IntentType.unknown):
            rules.append(f"{num_cols[0]}最高的前几名是哪些？")

        # 规则4：有异常值可检测
        if num_cols and intent_result and intent_result.intent_type not in (IntentType.anomaly, IntentType.unknown):
            for col in num_cols[:2]:
                q75, q25 = df[col].quantile(0.75), df[col].quantile(0.25)
                iqr = q75 - q25
                if iqr > 0:
                    outliers = df[(df[col] < q25 - 1.5*iqr) | (df[col] > q75 + 1.5*iqr)]
                    if len(outliers) > 0:
                        rules.append(f"发现{len(outliers)}个异常值，需要分析原因？")
                        break

    # 去重
    seen = set()
    unique_rules = []
    for r in rules:
        key = r[:6]
        if key not in seen:
            seen.add(key)
            unique_rules.append(r)
    rules = unique_rules

    # LLM 补充（仅当规则不足时）
    if len(rules) < 2:
        try:
            import json
            llm_followups = await llm_client.chat([
                {"role": "system", "content": FOLLOWUP_PROMPT},
                {"role": "user", "content": f"用户问题: {question}\\n数据: {len(df) if df is not None else 0}行 {list(df.columns) if df is not None else '空'}"},
            ])
            content = llm_followups.get("content", "[]").strip()
            if content.startswith("'''"):
                content = content.split("\\n", 1)[1].rsplit("\\n", 1)[0]
            llm_rules = json.loads(content)
            if isinstance(llm_rules, list):
                rules.extend(llm_rules[:2])
        except Exception:
            pass

    return rules[:4]

'''

# Check if we need to append the function or if it already has it
if in_func:
    new_lines.append(new_func_body)
else:
    # The function might have been already written by the line-based approach
    # Just append it if not already present
    text_content = "".join(new_lines)
    if "基于实际数据动态生成" not in text_content:
        # Find the end of file and append
        new_lines.append("\n")
        new_lines.append(new_func_body)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("[OK] report_node.py followup generation improved")

print("=== All fixes applied! ===")
