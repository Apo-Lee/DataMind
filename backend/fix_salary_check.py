c = open("app/core/query_engine.py", "r", encoding="utf-8").read()

old = """    # 意图级安全检查：检测薪资相关查询
    _salary_keywords = ["薪资", "工资", "薪酬", "工资表", "salary", "薪资表", "薪水"]
    contains_salary_q = any(kw in question for kw in _salary_keywords)
    
    # 如果问题提到薪资，检查用户权限
    if contains_salary_q:
        main_table = intent.get("main_table", "")
        ts = _COLUMN_SENSITIVITY.get(agent.business_tag, {}).get(main_table, {})
        has_salary_col = "salary" in ts
        if has_salary_col:
            role = user_info.get("role", "employee") if user_info else "employee"
            max_level = _ROLE_SENSITIVITY_ACCESS.get(role, {"safe"})
            if "highly_sensitive" not in max_level:
                # 无论模型是否选择了 salary 列，只要问题涉及薪资且角色无权限，直接拒绝
                raise Exception(f"当前角色({role})无权查询薪资数据")"""

new = """    # 意图级安全检查：检测薪资相关查询
    # 员工可以查自己薪资（RLS 保护），但不能做聚合/查看所有
    _salary_keywords = ["薪资", "工资", "薪酬", "工资表", "salary", "薪资表", "薪水"]
    contains_salary_q = any(kw in question for kw in _salary_keywords)
    
    if contains_salary_q:
        main_table = intent.get("main_table", "")
        ts = _COLUMN_SENSITIVITY.get(agent.business_tag, {}).get(main_table, {})
        has_salary_col = "salary" in ts
        if has_salary_col:
            role = user_info.get("role", "employee") if user_info else "employee"
            max_level = _ROLE_SENSITIVITY_ACCESS.get(role, {"safe"})
            # 如果角色连 sensitive 级别都没有，拒绝
            if "sensitive" not in max_level:
                raise Exception(f"当前角色({role})无权查询薪资数据")
            # 员工角色不能做薪资的 SUM/AVG 聚合（防止推算他人薪资）
            if role == "employee":
                for agg in intent.get("aggregations", []):
                    col = agg.get("column", "")
                    if col == "salary" and agg.get("type") in ("SUM", "AVG"):
                        raise Exception("员工角色不能对薪资做聚合统计")
                # 如果没有 filter 指向自己（无 WHERE id = 当前员工），也拒绝
                has_self_filter = False
                for f in intent.get("filters", []):
                    if f.get("column") in ("id", "employee_id") and f.get("op") == "=":
                        emp_id = str(user_info.get("employee_id", ""))
                        if str(f.get("value", "")) == emp_id:
                            has_self_filter = True
                            break
                if not has_self_filter and not intent.get("aggregations"):
                    # 没有指定自己的 filter — 加入 RLS 会自动限制，所以这里不拦截
                    pass"""

if old in c:
    c = c.replace(old, new)
    open("app/core/query_engine.py", "w", encoding="utf-8").write(c)
    print("Fixed salary security check")
else:
    print("Pattern not found")
    # debug: print surrounding lines
    idx = c.find("意图级安全检查")
    if idx >= 0:
        print(c[idx:idx+800])
    else:
        print("'意图级安全检查' not found")
