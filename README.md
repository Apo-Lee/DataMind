# DataMind

> 更新时间: 2026-06-16 | 版本: 0.4.1

DataMind 是一个面向企业白领的 **AI 数据自助分析平台**。管理者做一次 HR 系统同步，业务人员即可用自然语言查询和分析自己权限内的业务数据。

**V4 核心改革**: 引入 **MCP (Model Context Protocol) Server 架构**，将每个业务系统封装为独立的 MCP Server（HR/CRM/费控/ERP），通过 **60 个结构化业务工具** 替代传统 SQL 生成，实现权限内建于工具、数据脱敏自动化的全新数据查询范式。

---

## 系统架构

用户 (HTTP Request) → POST /api/query/ask + JWT Token

**1. API 层** (app/api/query.py)
- 鉴权 → 获取用户身份 (role + data_scope)
- 意图解析 → LLM 判断查询意图
- 调用 mcp_safe_query() → 核心安全查询

**2. MCP 查询引擎** (app/core/query_engine.py)
- Step 2a: 意图解析 (LLM → 结构化 JSON)
- Step 2b: 权限校验 (PermissionEngine 校验)
- Step 2c: MCPClient.set_auth() → 注入权限上下文
- Step 2d: client.call_tool(business_tag, tool_name, params) → 调用 MCP 工具

**3. MCP Server 层** (进程内调用)
- HR MCP: 17 tools (组织架构/员工/绩效/考勤/人员变动)
- CRM MCP: 14 tools (客户/商机/跟进/销售目标)
- Finance MCP: 13 tools (费用/预算/成本中心/差旅)
- ERP MCP: 16 tools (库存/项目/采购/资源)
- MCPAuth: 列级可见性 + 行级 RLS + 数据脱敏

**4. 报告层** (app/core/reporter.py)
- LLM 撰写 Markdown 分析报告
- 简单查询: LLM 分析话语 + 数据表格
- 复杂查询: LLM 深度分析 + 业务建议 + 追问

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+ (前端, 可选)

### 安装

```bash
git clone https://github.com/Apo-Lee/DataMind.git
cd DataMind

# 后端
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
```

### 启动

```bash
cd backend
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
# 或使用 docker-compose up
```

### 测试

```bash
# 首次启动会自动初始化种子数据
# 登录账户:
#   admin / admin123 - 管理员, 全权限
#   emp1 / emp1@0001 - 技术总监, 团队范围
#   emp2 / emp2@0002 - 高级架构师, 仅自己

curl -X POST http://127.0.0.1:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username":"admin","password":"admin123"}'
```

---

## 核心功能

### 1. 自然语言查询

用户用中文提问，AI 自动理解意图并调用 MCP 工具查询数据：

- **直查**: "我的个人信息" → 调用 get_employee_detail
- **统计**: "各部门人力分布" → 调用 get_employee_distribution
- **排行**: "绩效排名最高的员工" → 调用 get_performance_ranking
- **趋势**: "近半年出勤率变化" → 调用 get_attendance_trend
- **对比**: "A 部门和 B 部门的预算对比" → 调用 get_department_budget

### 2. 智能权限控制

每用户拥有独立角色和数据范围，MCP 工具在内部自动执行：

- **角色**: admin / hr_director / finance_bp / dept_ceo / dept_manager / employee / viewer
- **列级可见性**: 薪资(salary) → 仅 admin/hr_director 可见; 手机号(phone) → 脱敏显示
- **行级 RLS**: 普通员工仅看自己; 部门经理看团队; 总监看部门及下属
- **数据脱敏**: 手机号保留前3后4; 邮箱保留前2位

### 3. LLM 生成分析报告

每次查询都经过 LLM 处理，生成包含以下结构的 Markdown 报告：

- 分析结论 (2-3 句核心洞察，加粗关键数字)
- 关键数据 (Markdown 表格)
- 分析洞察 (均值/中位数/标准差/趋势等统计指标)
- 业务建议 (1-3 条可操作建议)
- 追问建议 (动态生成的后续问题)

### 4. 深度分析

- **简单查询**: LLM 摘要 + 数据表格 (默认)
- **复杂查询**: LLM 深度分析 + 图表 + 业务建议 (趋势/对比/异常检测)

---

## API 文档

### 核心 API

| 端点 | 方法 | 功能 |
|------|------|------|
| /api/auth/login | POST | 登录获取 JWT Token |
| /api/query/ask | POST | 发起自然语言查询 |
| /api/query/history | GET | 获取查询历史 |
| /api/datasources | GET | 获取可用数据源 |
| /api/agent/ask | POST | LangGraph Agent 入口 |

### 请求体 (/api/query/ask)

```json
{
  "question": "各部门预算情况",
  "datasource_id": "982a161a-945a-4c59-b6ce-7fd374e97967"
}
```

### 响应

```json
{
  "report_markdown": "# ... Markdown 格式报告 ...",
  "intent": "aggregation",
  "analysis_depth": "simple",
  "insights": [...],
  "conversation_id": "..."
}
```

---

## 项目结构

```
DataMind/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由
│   │   │   ├── query.py      # 问答接口
│   │   │   ├── agent.py      # LangGraph Agent 接口
│   │   │   ├── auth.py       # 登录注册
│   │   │   └── admin/        # 管理后台
│   │   ├── core/
│   │   │   ├── query_engine.py   # 查询引擎 (mcp_safe_query)
│   │   │   ├── reporter.py       # LLM 报告生成
│   │   │   ├── auth.py           # JWT 鉴权
│   │   │   ├── llm_client.py     # DeepSeek API 客户端
│   │   │   ├── permissions.py    # 权限检查
│   │   │   └── hr_sync.py        # HR 同步引擎
│   │   ├── mcp_servers/
│   │   │   ├── base_sql.py       # MCP Server 基类 + MCPAuth 权限
│   │   │   ├── hr_server.py      # HR MCP Server (17 tools)
│   │   │   ├── crm_server.py     # CRM MCP Server (14 tools)
│   │   │   ├── finance_server.py # Finance MCP Server (13 tools)
│   │   │   ├── erp_server.py     # ERP MCP Server (16 tools)
│   │   │   ├── registry.py       # MCP Server 注册表
│   │   │   └── __init__.py       # 基类定义
│   │   ├── mcp_client.py         # MCP 客户端 (权限注入)
│   │   ├── orchestrator/         # LangGraph Agent 编排
│   │   │   ├── __init__.py       # OrchestratorAgent 主入口
│   │   │   ├── nodes/
│   │   │   │   ├── sql_node.py   # MCP 工具调用节点
│   │   │   │   ├── intent_node.py
│   │   │   │   ├── analysis_node.py
│   │   │   │   └── report_node.py
│   │   │   └── graph/
│   │   │       └── builder.py    # StateGraph 图构建
│   │   ├── models/               # SQLAlchemy ORM 模型
│   │   ├── schemas/              # Pydantic 请求/响应
│   │   ├── seed.py               # 种子数据
│   │   └── main.py               # FastAPI 入口
│   ├── demo_data/                # SQLite 数据库
│   └── requirements.txt
├── _test_agent_multi_role.py     # 39 个多角色测试
└── README.md
```

---

## 权限体系

### 角色定义

| 角色 | 数据范围 | 可查看 | 说明 |
|------|----------|--------|------|
| admin | 全部 | 一切数据 | 系统管理员 |
| hr_director | 部门及下属 | HR 全量 + 脱敏薪资 | HR 总监 |
| finance_director | 全部 | 财务全量 | 财务总监 |
| finance_bp | 部门 | 部门内费用 | 财务 BP |
| dept_ceo | 团队 | 部门 + CRM | 部门负责人 |
| dept_manager | 团队 | 部门内数据 | 子部门经理 |
| sales_manager | 团队 | CRM + 下属考勤 | 区域销售经理 |
| employee | 仅自己 | 个人 HR 信息 (无薪资) | 普通员工 |
| viewer | 部门 | HR 只读 | 只读用户 |

### 敏感字段分级

- **highly_sensitive**: salary (薪资) — 仅 admin/hr_director 可见
- **sensitive**: phone, email, budget — 脱敏后对 dept_ceo/dept_manager 可见
- **safe**: name, position, dept_id — 所有角色可见

---

## MCP 工具列表

### HR 系统 (17 tools)
- get_org_structure, get_department_detail, get_department_budget
- get_employee_detail, search_employees, get_employee_distribution, get_new_hires
- get_performance_overview, get_performance_ranking
- get_attendance_summary, get_attendance_detail, get_attendance_trend
- get_headcount_trend
- 以及核心工具: query, execute_sql, list_tables, describe_table

### CRM 系统 (14 tools)
- get_sales_pipeline, get_deal_detail, search_deals, get_deal_stage_summary
- get_customer_detail, search_customers, get_customer_distribution
- get_sales_forecast, get_team_performance
- get_follow_up_list
- query, execute_sql, list_tables, describe_table

### 费控系统 (13 tools)
- get_expense_summary, get_expense_detail, get_expense_by_category
- get_budget_overview, get_budget_detail, get_budget_execution
- get_cost_center_summary, get_cost_center_detail
- get_travel_expense_summary
- query, execute_sql, list_tables, describe_table

### ERP 系统 (16 tools)
- get_inventory_status, get_inventory_alert, get_inventory_by_warehouse
- get_project_summary, get_project_detail, get_project_progress, get_project_cost
- get_purchase_order_summary, get_purchase_order_detail
- get_resource_allocation
- query, execute_sql, list_tables, describe_table

---

## 测试

```bash
# 39 个多角色测试 (直接调用 MCP Server)
cd backend
.venv\Scripts\python ../_test_agent_multi_role.py

# 端到端 API 测试 (需要启动服务)
.venv\Scripts\python _e2e_full.py
```

---

## License

MIT
