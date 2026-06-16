# -*- coding: utf-8 -*-
"""Apply all fixes correctly"""

path = 'E:\\Python_Code_Project\\DataMind\\backend\\app\\core\\query_engine.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ===== 1. Replace prompt =====
pi = content.index('_QUERY_INTENT_PROMPT = ')
q1 = content.index('\"\"\"', pi + 28) + 3  # opening quotes
# The prompt ends at the NEXT triple-quote (there is one right after the prompt)
cq = content.index('\"\"\"', q1)  # This is the CORRECT closing quote for the prompt

new_prompt = '''_QUERY_INTENT_PROMPT = \"\"\"你是一个数据查询意图解析专家。根据用户的问题和下面的数据库结构，输出结构化的查询意图 JSON。

输出的 JSON 将被转换为 SQL，请严格遵守以下规则。

[数据库结构]
{tables_desc}

[通用规则(必须遵守)]
1. 列名必须使用实际名称，不要编造。例如 department_id 不存在，正确是 dept_id。
2. 过滤条件的值必须用 [可能值] 中列出的中文值，不能用英文。
3. 日期用 YYYY-MM-DD 格式。
4. 列名不要带表前缀(写 name 而不是 employees.name)。
5. 聚合函数(COUNT/SUM/AVG)放在 aggregations，不要放 select_columns。
6. 复杂计算(出勤率等)用 expression 字段写 CASE WHEN 表达式。

[常见查询模式]
- 总人数: aggregations: [{type:COUNT}]
- 各部门人数: 先 join departments，用 departments 的 name 分组
- 某部门人数: join departments，filters 用 name 过滤
- 出勤率: expression 写 SUM(CASE WHEN status=出勤 THEN 1 ELSE 0 END)*100.0/COUNT(*)
- 近N月入职: filters 用 join_date >= 日期

[表关系]
departments.id <- employees.dept_id
employees.id <- attendance.employee_id
customers.id <- deals.customer_id
projects.id <- resources.project_id
跨表查询必须在 join_tables 中填关联表名

[输出格式(严格JSON)]
{
    "question_type": "count|aggregation|list|trend",
    "main_table": "主表名",
    "join_tables": ["关联表(跨表查询必填)"],
    "select_columns": ["列名"],
    "aggregations": [{"type":"COUNT","column":"","alias":"total"}],
    "filters": [{"column":"列名","op":"=","value":"(用可能值中的值)"}],
    "group_by": ["分组列名"],
    "order_by": [{"column":"列名","direction":"ASC"}],
    "limit": 1000,
    "expression": "CASE WHEN等简单聚合不用",
    "explanation": "中文解释"
}
\"\"\"
'''

content = content[:pi] + new_prompt + content[cq+3:]

# ===== 2. Add FK relations between config and prompt =====
fk_insert = content.index('_QUERY_INTENT_PROMPT = ')
fk_block = '''
# 预定义外键关系
_FOREIGN_KEY_RELATIONS = {
    "hr": {
        ("employees", "departments"): ("dept_id", "id"),
        ("departments", "employees"): ("id", "dept_id"),
        ("attendance", "employees"): ("employee_id", "id"),
        ("employees", "attendance"): ("id", "employee_id"),
    },
    "crm": {
        ("deals", "customers"): ("customer_id", "id"),
        ("customers", "deals"): ("id", "customer_id"),
        ("follow_ups", "customers"): ("customer_id", "id"),
        ("follow_ups", "employees"): ("employee_id", "id"),
    },
    "finance": {
        ("expenses", "budgets"): ("dept_id", "dept_id"),
        ("travel_expenses", "expenses"): ("expense_id", "id"),
    },
    "erp": {
        ("resources", "projects"): ("project_id", "id"),
        ("projects", "departments"): ("dept_id", "id"),
        ("purchase_orders", "employees"): ("requester_id", "id"),
    },
}
'''

content = content[:fk_insert] + fk_block + content[fk_insert:]

# ===== 3. Replace _build_tables_desc =====
td_start = content.index('def _build_tables_desc')
pq_start = content.index('\nasync def parse_query_intent', td_start) + 1

new_td = '''def _build_tables_desc(agent) -> str:
    """生成全面的表结构描述，包含枚举值、外键、行数"""
    tables = agent.list_tables()
    tag = agent.business_tag
    parts = []

    # 表清单
    part1 = ['[可用表]']
    for t in tables:
        try:
            df = agent.execute_sql('SELECT COUNT(*) AS cnt FROM "' + t + '"')
            rc = int(df.iloc[0, 0]) if not df.empty else 0
        except Exception:
            rc = 0
        part1.append('  - ' + t + ' (' + str(rc) + '行)')
    parts.append(chr(10).join(part1))

    # 各表详细字段
    detail = ['', '[各表字段]']
    for t in tables:
        ts = agent.describe_table(t)
        try:
            df2 = agent.execute_sql('SELECT COUNT(*) AS cnt FROM "' + t + '"')
            rc = int(df2.iloc[0, 0]) if not df2.empty else 0
        except Exception:
            rc = 0
        detail.append('')
        detail.append('  ' + t + ' (' + str(rc) + '行):')
        for c in ts.columns:
            desc = c.name + ' ' + c.dtype
            if c.is_primary_key:
                desc += ' PK'
            try:
                dfv = agent.execute_sql(
                    'SELECT DISTINCT "' + c.name + '" FROM "' + t + '" WHERE "' + c.name + '" IS NOT NULL ORDER BY 1'
                )
                if dfv is not None and not dfv.empty:
                    vals = [str(v) for v in dfv.iloc[:, 0].tolist() if str(v) != 'nan']
                    if len(vals) <= 15 and len(vals) > 0:
                        desc += ' [可能值: ' + ', '.join(vals) + ']'
                    elif vals:
                        desc += ' 例如: ' + ', '.join(vals[:4])
            except Exception:
                pass
            if c.name.endswith('_id') and not c.is_primary_key and c.name != 'parent_dept_id':
                singular = c.name[:-3]
                for at in tables:
                    if at == singular or at == singular + 's' or at == singular + 'es':
                        desc += ' -> ' + at + '.id'
                        break
            detail.append('    - ' + desc)
        detail.append('')
    parts.append(chr(10).join(detail))

    # 外键关系
    relations = _FOREIGN_KEY_RELATIONS.get(tag, {})
    if relations:
        rel_part = ['', '[表关系]']
        for (t1, t2), (fk, pk) in relations.items():
            rel_part.append('  ' + t1 + '.' + fk + ' = ' + t2 + '.' + pk)
        parts.append(chr(10).join(rel_part))

    return chr(10).join(parts)
'''

content = content[:td_start] + new_td + content[pq_start:]

# ===== 4. Add _resolve_column and __init__ enhancements =====
content = content.replace(
    'def __init__(self, user_info: dict, business_tag: str):',
    'def __init__(self, user_info: dict, business_tag: str, agent=None):'
)

init_marker = 'self.max_level = _ROLE_SENSITIVITY_ACCESS.get(user_info.get("role", "employee"), {"safe"})'
init_extra = '''
        self._real_columns = {}
        self._column_synonyms = {
            "department_id": "dept_id",
            "department_name": "name",
            "employee_name": "name",
            "emp_id": "id",
        }
        if agent:
            try:
                for t in agent.list_tables():
                    ts = agent.describe_table(t)
                    self._real_columns[t] = [c.name for c in ts.columns]
            except Exception:
                pass'''

content = content.replace(init_marker, init_marker + init_extra)

# Add _resolve_column before build
build_marker = '\n    def build(self, intent: dict) -> str:\n'
resolve_method = '''
    def _resolve_column(self, table: str, col: str) -> str:
        """校验并修正列名：将 LLM 可能输出的错误列名映射为真实列名"""
        if not table or table not in self._real_columns:
            return col
        real_cols = self._real_columns[table]
        if col in real_cols:
            return col
        if col in self._column_synonyms:
            mapped = self._column_synonyms[col]
            if mapped and mapped in real_cols:
                return mapped
        col_lower = col.lower()
        for rc in real_cols:
            if rc.lower() == col_lower:
                return rc
        if "." in col:
            bare_col = col.split(".")[-1]
            if bare_col in real_cols:
                return bare_col
        return col

'''

content = content.replace(build_marker, resolve_method + build_marker)

# ===== 5. Remove redundant filter loop =====
uc_idx = content.find('user_conds = []')
if uc_idx > 0:
    uc_line_start = content.rfind('\n', 0, uc_idx) + 1
    before = content[uc_line_start:uc_idx]
    if before.strip().startswith('#'):
        comment_start = content.rfind('\n', 0, uc_line_start - 2) + 1
        uc_line_start = comment_start
    ext_end = content.find('\n', content.find('all_conds.extend(user_conds)')) + 1
    content = content[:uc_line_start] + content[ext_end:]

# ===== 6. Verify =====
try:
    compile(content, 'query_engine.py', 'exec')
    print('COMPILE OK')
except SyntaxError as e:
    print(f'ERROR line {e.lineno}: {e.msg}')
    lines = content.split('\n')
    if e.lineno and e.lineno <= len(lines):
        print(f'  {repr(lines[e.lineno-1][:120])}')
    raise

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('ALL FIXES APPLIED')
