# DataMind

> 更新时间: 2026-06-16 | 版本: 0.4.0

DataMind 是一个面向企业白领的 **AI 数据自助分析平台**。管理者做一次 HR 系统同步，业务人员即可用自然语言查询和分析自己权限内的业务数据。

**V4 核心改革**: 引入 **MCP (Model Context Protocol) Server 架构**，将每个业务系统封装为独立的 MCP Server（HR/CRM/费控/ERP），通过 **60 个结构化业务工具** 替代传统 SQL 生成，实现权限内建于工具、数据脱敏自动化的全新数据查询范式。

---

## 系统架构

`
用户 (HTTP Request)
     │ POST /api/query/ask + JWT Token
     ▼
┌────────────────────────────────────────────────────────┐
│  1. API 层 (app/api/query.py)                           │
│     ├─ 鉴权 → 获取用户身份 (role + data_scope)         │
│     ├─ 意图解析 → LLM 判断查询意图                      │
│     └─ 调用 mcp_safe_query() → 核心安全查询              │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  2. MCP 查询引擎 (app/core/query_engine.py)             │
│                                                         │
│  Step 2a: 意图解析       Step 2b: 权限校验              │
│  LLM → 结构化 JSON       PermissionEngine 校验          │
│       │                        │                        │
│       └────────┬───────────────┘                        │
│                ▼                                        │
│  Step 2c: MCPClient.set_auth() → 注入权限上下文         │
│  Step 2d: client.query(business_tag, params)            │
│                │                                        │
│                ▼                                        │
│  ┌─────────────────────────────────────────┐            │
│  │  3. MCP Server 层 (进程内调用)           │            │
│  │                                          │            │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │            │
│  │  │ HR MCP   │ │ CRM MCP  │ │Finance   │ │            │
│  │  │ 17 tools │ │ 14 tools │ │ 13 tools │ │            │
│  │  └──────────┘ └──────────┘ └──────────┘ │            │
│  │  ┌──────────┐ ┌──────────────────────┐  │            │
│  │  │ ERP MCP  │ │ MCPAuth 权限控制     │  │            │
│  │  │ 16 tools │ │ • 列级可见性          │  │            │
│  │  └──────────┘ │ • 行级 RLS            │  │            │
│  │               │ • 数据脱敏             │  │            │
│  │               └──────────────────────┘  │            │
│  └─────────────────────────────────────────┘            │
│                │                                        │
│                ▼                                        │
│  Step 2e: 数据脱敏 → mask_sensitive_data()              │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  4. 报告层 (app/core/reporter.py)                       │
│     LLM 撰写 Markdown 分析报告                           │
│     - 简单查询: LLM 摘要 + 数据表格                      │
│     - 复杂查询: LLM 深度分析 + 图表 + 业务建议           │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
                    响应返回 (report_markdown + insights)
`

## MCP Server 架构

### 设计理念

摒弃传统「NL → SQL」模式，改为 **MCP 工具调用** 架构：

| 传统模式 | MCP 模式 |
|---------|---------|
| LLM 生成 SQL → 执行 → 脱敏 | LLM 选择工具 → 调用工具 → 工具自带权限 |
| 权限是事后过滤 | 权限内建于工具 |
| SQL 注入风险 | 结构化参数，天然防注入 |
| 每次查询重新解析表结构 | 工具定义明确，参数类型安全 |

### 4 大 MCP Server · 60 个业务工具

**HR 系统 (17 tools)**

| 工具 | 功能 |
|------|------|
| query | 结构化核心查询 (SELECT/聚合/过滤/分组/JOIN) |
| get_org_structure | 完整组织架构树（部门层级、负责人、人数） |
| get_department_detail | 单个部门详细信息（成员列表、预算、负责人） |
| get_department_budget | 各部门预算情况 |
| get_employee_detail | 员工详细信息（基本信息、部门、绩效、联系方式） |
| search_employees | 按条件搜索员工（部门/职位/职级/状态/性别/学历） |
| get_employee_distribution | 员工分布统计（按部门/职位/职级/性别/学历分组） |
| get_new_hires | 新员工列表（按入职日期范围） |
| get_performance_overview | 绩效概览（平均分/最高/最低/分布） |
| get_performance_ranking | 绩效排名 |
| get_attendance_summary | 考勤汇总 |
| get_attendance_detail | 考勤明细 |
| get_attendance_trend | 考勤趋势 |
| get_headcount_trend | 人员增长趋势 |
| list_tables | 列出所有表和字段 |
| describe_table | 查看表结构 |
| execute_sql | 受限原始 SQL |

**CRM 系统 (14 tools)**

| 工具 | 功能 |
|------|------|
| search_customers | 搜索客户（按行业/等级/负责人/关键字） |
| get_customer_detail | 客户详细信息（基本信息、关联商机、跟进记录） |
| get_customer_distribution | 客户分布统计（按行业/等级） |
| get_sales_pipeline | 销售管道概览（按阶段汇总商机数量和金额） |
| search_deals | 搜索商机（按状态/阶段/金额/负责人/时间范围） |
| get_deal_summary | 商机汇总统计（赢单率/总金额/平均金额） |
| get_follow_ups | 跟进记录（按客户/负责人/类型筛选） |
| get_sales_targets | 销售目标完成情况 |
| get_team_performance | 团队业绩排名 |
| get_deal_performance_ranking | 商工业绩排名 |

**费控系统 (13 tools)**

| 工具 | 功能 |
|------|------|
| get_budget_overview | 预算总览（按部门/年度/季度汇总） |
| get_budget_detail | 预算明细（按类别/预算类型） |
| get_budget_execution_rate | 预算执行率排名 |
| get_expense_summary | 费用汇总（按类别/部门） |
| search_expenses | 搜索费用记录（按类别/状态/部门/金额/时间） |
| get_expense_trend | 费用趋势（按月统计） |
| get_travel_expenses | 差旅费用明细 |
| get_travel_summary | 差旅汇总（按目的地/员工） |
| get_cost_centers | 成本中心情况 |

**ERP 系统 (16 tools)**

| 工具 | 功能 |
|------|------|
| get_project_overview | 项目总览（按状态/优先级汇总） |
| search_projects | 搜索项目（按状态/优先级/部门/时间范围） |
| get_project_detail | 项目详细信息（含参与部门、资源分配） |
| get_project_budget_analysis | 项目预算分析（预算 vs 实际 vs 偏差率） |
| get_project_timeline | 项目时间线 |
| get_resource_allocation | 资源分配情况 |
| get_resource_cost_analysis | 资源成本分析 |
| get_inventory_status | 库存状态（支持低库存预警） |
| get_inventory_summary | 库存汇总（按仓库/类别） |
| get_low_stock_alerts | 低库存预警 |
| search_purchase_orders | 搜索采购订单 |
| get_purchase_summary | 采购汇总 |

### 权限控制三层模型

`
┌─────────────────────────────────────────────┐
│  1. 列级可见性 (Column-Level Access)         │
│     highly_sensitive: salary, phone, email    │
│     sensitive: budget                         │
│     safe: name, dept_id, position...          │
│                                               │
│  2. 行级 RLS (Row-Level Security)             │
│     self_only → employee_id = 当前用户        │
│     team/dept → dept_id = 当前部门            │
│     dept_and_sub → 部门树递归                 │
│     all → 无限制                               │
│                                               │
│  3. 数据脱敏 (Data Masking)                   │
│     phone: 138****0001                        │
│     email: zh***@demo.com                     │
│     salary: ***                                │
└─────────────────────────────────────────────┘
`

## 权限体系

### 角色映射

| 职位 | 系统角色 | 敏感级别 | 默认行级范围 |
|------|---------|---------|-------------|
| 系统管理员 | admin | safe+sensitive+highly_sensitive | all |
| HR 总监 | hr_director | safe+sensitive+highly_sensitive | all |
| 财务总监 | finance_director | safe+sensitive | all (跨部门) |
| 财务人员 | finance_bp | safe+sensitive | 本部门 |
| 部门 CEO | dept_ceo | safe+sensitive | 本部门及子部门 |
| 经理/主管 | dept_manager | safe+sensitive | 直属下级 |
| 区域销售经理 | sales_manager | safe+sensitive | 直属下级 |
| 普通员工 | employee | safe | 仅自己 |
| 访客 | viewer | safe | 本部门 |

### 数据范围 (data_scope)

| scope | 含义 |
|-------|------|
| self_only | 仅看到自己的数据 |
| 	eam | 直属下级 + 自己 (默认) |
| dept | 本部门 (平级所有同事) |
| dept_and_sub | 本部门及所有子部门 |
| cross_dept | 跨部门 (额外配置) |
| ll | 全公司 |

## 快速启动

`ash
# 1. 克隆并安装后端依赖
git clone https://github.com/Apo-Lee/DataMind.git
cd DataMind/backend
pip install -r requirements.txt

# 2. 生成演示数据库
cd ..
uv run python demo_data/seed_unified_v2.py

# 3. 初始化系统 (创建管理员 + 数据源 + HR 同步)
cd backend
uv run python -c "import asyncio; from app.seed import seed; asyncio.run(seed())"

# 4. 启动后端
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 5. 启动前端 (新终端)
cd frontend
npm install
npx vite --host 127.0.0.1 --port 5173

# 6. 浏览器打开
# http://localhost:5173
# 管理员: admin / admin123
`

## 测试

`ash
cd backend

# 多角色 Agent 全链路测试 (39 个场景)
uv run python ../_test_agent_multi_role.py

# 单元测试
uv run python -m pytest tests/ -v

# Agent 编排专项测试
uv run python -m pytest tests/test_agent_orchestrator.py -v

# 行级安全专项测试
uv run python -m pytest tests/test_row_level_security.py -v
`

## 演示数据

| 系统 | 数据规模 |
|------|---------|
| HR 系统 | 191 员工, 17 部门 (含父子层级), 24,440 考勤 |
| CRM 系统 | 800 客户, 3,000 交易, 4,000 跟进, 212 销售目标 |
| 费控系统 | 181 预算, 3,000 费用, 600 差旅明细, 17 成本中心 |
| ERP 系统 | 20 项目, 250 资源, 500 库存, 300 采购订单 |

## 项目结构

`
DataMind/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI 路由
│   │   │   └── query.py       # 问答 API (MCP 查询入口)
│   │   ├── core/
│   │   │   ├── query_engine.py  # 查询引擎 (意图解析 + MCP 调用)
│   │   │   ├── permissions.py   # 权限引擎
│   │   │   ├── reporter.py      # 报告组装
│   │   │   ├── auth.py          # JWT 鉴权
│   │   │   └── llm_client.py    # LLM 客户端
│   │   ├── mcp_servers/         # MCP Server 实现
│   │   │   ├── base_sql.py      # 基类 + MCPAuth 权限系统
│   │   │   ├── hr_server.py     # HR MCP Server (17 tools)
│   │   │   ├── crm_server.py    # CRM MCP Server (14 tools)
│   │   │   ├── finance_server.py# 费控 MCP Server (13 tools)
│   │   │   ├── erp_server.py    # ERP MCP Server (16 tools)
│   │   │   └── registry.py      # Server 注册表
│   │   ├── mcp_client.py        # MCP 客户端 (权限注入)
│   │   ├── agents/              # Agent 工厂
│   │   ├── orchestrator/        # LangGraph 编排
│   │   ├── models/              # SQLAlchemy 模型
│   │   └── seed.py              # 系统初始化种子
│   └── tests/                   # 单元测试
├── demo_data/                   # 演示数据库
├── frontend/                    # Vue 3 前端
└── _test_agent_multi_role.py    # 多角色集成测试
`

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/query/ask | 自然语言查询 (MCP 全链路) |
| GET | /api/query/history | 查询历史列表 |
| GET | /api/query/history/{id} | 查询历史详情 |
| POST | /api/auth/login | 登录获取 JWT Token |
| GET | /api/dashboard | BI 驾驶舱 |
| GET | /api/admin/users | 用户管理 |
| GET | /api/mcp/servers | MCP Server 列表 |
| GET | /api/mcp/{tag}/tools | 查看某个 Server 的工具 |
| POST | /api/mcp/{tag}/execute | 执行某个工具 |

## V4 相比 V3 的变化

- **MCP Server 架构**: 4 个独立 MCP Server (HR/CRM/费控/ERP)，60 个业务工具
- **权限内建于工具**: MCPAuth 统一控制列级可见性 + 行级 RLS + 数据脱敏
- **去除 SQL 生成**: Agent 不再生成 SQL，而是调用结构化工具
- **全面错误修复**: int(None) 错误、编码损坏、语法错误、脱敏类型安全检查
- **多角色验证**: 39 个测试场景覆盖 7 种角色，100% 通过

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 (async) + DeepSeek API + LangGraph
- **MCP 框架**: 自定义进程内 MCP 实现 (BaseMCPServer + MCPTool + MCPAuth)
- **前端**: Vue 3 + Vite + Element Plus + ECharts + Pinia
- **数据库**: SQLite (开发) / PostgreSQL 15 (生产)
- **元数据库**: HR 数据锚点 + 用户权限
