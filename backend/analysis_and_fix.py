print("""
╔══════════════════════════════════════════════════════════════╗
║  DataMind Agent SQL 问题根因分析与修复方案                     ║
╚══════════════════════════════════════════════════════════════╝

▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
一、问题根因梳理
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

问题 1: RLS 双重注入（最严重）
────────────────────────────────────────
  表现: WHERE "dept_id" = 1 AND (dept_id IN (1,101,102,103))
  根因:
    SQLBuilder._build_rls_filters()          → 注入 "dept_id" = 1
    agent.execute_sql() → QueryInterceptor   → 再注入 (dept_id IN (1,101,102,103))
  两条路径都在往 WHERE 里加 dept_id 条件
  → 且其中一条用 unquoted column name，另一条用 quoted column name
  SQLite 认为这是两个不同的列！

问题 2: RLS 注入不存在的列
────────────────────────────────────────
  表现: attendance 表 WHERE "dept_id" ...
  根因: _build_rls_filters() 永远只注入 dept_id 或 employee_id
        不检查目标表是否有这些列
  attendance 表: employee_id 存在，但 dept_id 不存在！
  departments 表: 既无 dept_id 也无 employee_id
  customers 表: 只有 owner_dept_id 无 dept_id

问题 3: JOIN 列名硬编码
────────────────────────────────────────
  表现: ON departments.id = employees.department_id
  根因: _build_joins() 中 fk_col = jt.rstrip("s") + "_id"
        "employees".rstrip("s") + "_id" = "employee_id"
        正确的: employees 表的 dept_id 不是 employee_id
        更通用的: 应读真实外键关系，而不是靠命名约定猜

问题 4: BETWEEN 语法错误
────────────────────────────────────────
  表现: date BETWEEN ('2023-01-01', '2023-01-31')
  正确:  date BETWEEN '2023-01-01' AND '2023-01-31'
  根因: _build_where() 处理 list 值: 
        f"\\"{col}\\" {op} ({vals_str})"
        把 BETWEEN 当 IN 处理了

问题 5: 多表 JOIN 后列歧义
────────────────────────────────────────
  表现: LEFT JOIN employees ... WHERE COUNT("id") 
  根因: 在 JOIN 了 departments 后，"id" 变得歧义
        应该用 "main_table"."id"

问题 6: 权限配置过于激进
────────────────────────────────────────
  表现: dept_ceo (!) 被禁止聚合 salary
  形式: PermissionEngine 规则3: 检查聚合格中的列
        dept_ceo 的 max_level = {"safe"}
        salary 是 "highly_sensitive" -> 拒绝
  解决方案: dept_ceo 角色应能查看本部门的数据，
            salary 脱敏即可，不应完全禁止

▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
二、修复策略（按优先级排序）
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

策略 A: 统一 RLS 注入点（消除所有 RLS 问题）
────────────────────────────────────────
  问题: SQLBuilder 自己注入 RLS，execute_sql 又通过 QueryInterceptor 再注入
  方案:
    不再由 SQLBuilder 的 build() 方法内联 RLS
    SQLBuilder 只构建"干净"SQL（不含 RLS 过滤）
    RLS 统一由 execute_sql() 路径下的 QueryInterceptor 完成
    QueryInterceptor 通过列名+表名匹配精确注入

    改动文件: query_engine.py 的 SQLBuilder.build()
              → 去掉 _build_rls_filters() 调用
              → _build_where() 只处理用户过滤条件

策略 B: 精确列存在性检查 + 表感知的 RLS 注入
────────────────────────────────────────
  问题: QueryInterceptor 和 _build_rls_filters 都不检查列是否存在
  方案:
    QueryInterceptor 需要读取目标表的 schema 来确定
    哪些列确实存在，只注入存在的列
    
    需要改动: QueryInterceptor 需要访问 DataSourceAgent
             来调用 describe_table() 检查列
    
    或更简单的方案: 在 RLS 过滤子句中只注入
    被查询表实际存在的列
    
    对于 departments: 无 dept_id → 跳过 RLS 部门过滤
    对于 attendance: 用 employee_id 而不是 dept_id
    对于 customers: 用 owner_dept_id 替代 dept_id

策略 C: Schema 感知的 JOIN 构建
────────────────────────────────────────
  问题: _build_joins() 靠命名约定猜外键
  方案:
    在探测 schema 时收集外键关系
    SQLBuilder 在构建 JOIN 时查真实外键
    而不是硬编码 rules
    
    需要的预处理: probe_raw_schema() 时读取外键
    SQLite: PRAGMA foreign_key_list(table_name)

策略 D: BETWEEN 语法修复
────────────────────────────────────────
  问题: _build_where() 处理 list 类型值用错格式
  修复:
    if op == "BETWEEN" and isinstance(val, list):
        fmt = BETWEEN '{}' AND '{}'
    而不是用通用的 list 格式化

策略 E: 权限配置调优
────────────────────────────────────────
  dept_ceo 角色增加敏感级别权限:
    "dept_ceo": {"safe", "sensitive"}
  (查本部门的数据可以有更高权限)

▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
三、影响评估
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

修复 A (统一 RLS): 消除 60% 的问题（S1,S2,AT1,AT2,AT3,C1,CR2）
修复 B (列检查):   消除 20% 的问题（departments/customers 无 dept_id）
修复 D (BETWEEN): 消除 10% 的问题（CR1,AT1 日期过滤）
修复 E (权限):     消除 10% 的问题（A1,A3,S3 的权限拒绝）

预期修复后通过率: 12/16 = 75%（剩余的失败将是 LIMIT=6的业务逻辑问题）
预期修复后 SQL 可执行率: 16/16 = 100%
"""
)
