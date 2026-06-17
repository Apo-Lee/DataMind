# DataMind

DataMind 是一个面向企业白领的 **AI 数据自助分析平台**。一次 HR 系统同步后，业务人员即可用自然语言查询和分析自己权限内的业务数据，无需学习 SQL。
![UI_1.png](UI_1.png)

---

## 它能做什么

用中文提问，AI 理解你的意图，在你权限范围内查询数据，生成带分析的报告：

**数据查询**

- "各部门预算情况" → 返回各部门预算排名与占比分析
- "我的个人信息" → 返回你的个人档案（入职、绩效等）
- "绩效排名最高的员工" → 返回绩效 Top 员工名单

**权限控制**

- "我的薪资情况" → 员工可查看自己薪资（脱敏显示）
- "我部门人效趋势" → 部门负责人只看到自己团队的数据
- "其他人的薪资" → 被权限系统拦截

**智能报告**

每次查询都会生成结构化的 Markdown 报告，包含分析结论、数据表格和业务建议。

---

## 架构

```
用户 → HTTP POST /api/query/ask + JWT Token
                │
        ┌───────┴────────┐
        │  API 层         │  鉴权 → check_datasource_access
        └───────┬────────┘
                │
        ┌───────┴────────┐
        │ Orchestrator    │  LangGraph StateGraph 编排
        │ (统一入口)       │  intent_node → sql_node → analysis_node → report_node
        └───────┬────────┘
                │
        ┌───────┴────────┐
        │  MCP Server 层  │  HR / CRM / 费控 / ERP 业务工具
        │  + MCPAuth 权限  │  列级可见性 + 行级 RLS + 数据脱敏
        │  (contextvar)    │  请求级权限上下文，无并发竞态
        └───────┬────────┘
                │
        ┌───────┴────────┐
        │  报告层          │  LLM 生成 Markdown 分析报告
        └────────────────┘
```

核心设计：**单一发布入口**（`POST /api/query/ask`）委托 LangGraph OrchestratorAgent，内部经过意图识别 → SQL/Tools → 分析 → 报告 四个节点。

每个业务系统封装为独立的 MCP Server，暴露结构化业务工具（如 `get_department_budget`、`get_employee_detail`）。权限上下文通过 **contextvar** 在每个请求任务内隔离传递，修复了全局单例的并发竞态问题。

---

## 快速启动

### 环境要求

- **Python 3.12+**（后端）
- **Node.js 18+**（前端，可选）

### 后端

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（DeepSeek 平台获取）

# 启动（首次自动初始化种子数据）
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

首次启动会自动创建 SQLite 数据库、生成 4 个 demo 业务库、同步 189 个用户数据。

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 测试账户

| 用户名 | 密码 | 角色 | 数据范围 | 说明 |
|--------|------|------|----------|------|
| `admin` | `admin123` | 管理员 | 全部 | 系统管理员 |
| `emp1` | `emp1@0001` | 部门负责人 | 团队 | 技术研发中心 |
| `emp2` | `emp2@0002` | 普通员工 | 仅自己 | 高级架构师 |
| `emp31` | `emp31@0031` | 部门经理 | 团队 | AI 实验室 |

---

## 项目结构

```
DataMind/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── api/                # API 路由（auth、query、agent、dashboard）
│   │   │   └── query.py        # 统一查询入口（委托 OrchestratorAgent）
│   │   ├── core/               # 核心引擎
│   │   │   ├── auth.py         # JWT 鉴权 + 密钥强度校验
│   │   │   ├── auth_context.py # contextvar 权限上下文（P0 修复）
│   │   │   ├── query_engine.py # 敏感度映射常量（供 MCPAuth 使用）
│   │   │   ├── llm_client.py   # DeepSeek API 客户端
│   │   │   ├── permissions.py  # 数据源权限检查
│   │   │   ├── hr_sync.py      # HR 同步引擎
│   │   │   ├── encryption.py   # AES 加密
│   │   │   └── sandbox.py      # 代码沙箱
│   │   ├── mcp_servers/        # MCP Server 实现
│   │   │   ├── base_sql.py     # 基类 + MCPAuth 权限 (RLS/脱敏)
│   │   │   ├── hr_server.py    # HR 系统（17 个工具）
│   │   │   ├── crm_server.py   # CRM 系统（14 个工具）
│   │   │   ├── finance_server.py # 费控系统（13 个工具）
│   │   │   ├── erp_server.py   # ERP 系统（16 个工具）
│   │   │   └── registry.py     # 注册表 + HTTP 路由（已加鉴权）
│   │   ├── mcp_client.py       # MCP 客户端（contextvar 传递权限）
│   │   ├── orchestrator/       # LangGraph Agent 编排（统一入口）
│   │   │   ├── nodes/          # intent / sql / analysis / report 节点
│   │   │   ├── graph/          # StateGraph 构建
│   │   │   └── errors.py       # 友好的错误提示
│   │   ├── agents/             # 旧 Agent 实现（保留兼容）
│   │   ├── models/             # SQLAlchemy ORM（含全部 13 表）
│   │   ├── schemas/            # Pydantic 请求响应
│   │   ├── seed.py             # 种子数据
│   │   └── main.py             # FastAPI 入口
│   ├── scripts/                # 开发/调试脚本（gitignored）
│   ├── tests/                  # pytest 测试
│   │   ├── test_mcp_auth_rls.py    # MCPAuth 权限回归测试（20 用例）
│   │   ├── test_row_level_security.py
│   │   ├── test_sql_quality.py
│   │   ├── agents/
│   │   └── conftest.py
│   ├── demo_data/              # SQLite 示例数据库
│   └── requirements.txt
├── frontend/                   # Vue 3 + Vite 前端
└── README.md
```

---

## MCP 工具

4 个 MCP Server 共提供 **60 个业务工具**，统一的 `execute_tool` 覆写自动对结果集脱敏：

### HR 系统（17 个工具）

| 类别 | 工具 |
|------|------|
| 组织架构 | `get_org_structure`、`get_department_detail`、`get_department_budget` |
| 员工 | `get_employee_detail`、`search_employees`、`get_employee_distribution`、`get_new_hires` |
| 绩效 | `get_performance_overview`、`get_performance_ranking` |
| 考勤 | `get_attendance_summary`、`get_attendance_detail`、`get_attendance_trend` |
| 人员变动 | `get_headcount_trend` |

### CRM 系统（14 个工具）

| 类别 | 工具 |
|------|------|
| 商机 | `get_sales_pipeline`、`get_deal_detail`、`search_deals`、`get_deal_stage_summary` |
| 客户 | `get_customer_detail`、`search_customers`、`get_customer_distribution` |
| 销售 | `get_sales_forecast`、`get_team_performance` |
| 跟进 | `get_follow_up_list` |

### 费控系统（13 个工具）

| 类别 | 工具 |
|------|------|
| 费用 | `get_expense_summary`、`get_expense_detail`、`get_expense_by_category` |
| 预算 | `get_budget_overview`、`get_budget_detail`、`get_budget_execution` |
| 成本中心 | `get_cost_center_summary`、`get_cost_center_detail` |
| 差旅 | `get_travel_expense_summary` |

### ERP 系统（16 个工具）

| 类别 | 工具 |
|------|------|
| 库存 | `get_inventory_status`、`get_inventory_alert`、`get_inventory_by_warehouse` |
| 项目 | `get_project_summary`、`get_project_detail`、`get_project_progress`、`get_project_cost` |
| 采购 | `get_purchase_order_summary`、`get_purchase_order_detail` |
| 资源 | `get_resource_allocation` |

---

## 权限体系

### 安全设计

```
请求进入 → JWT 鉴权 → 从 User ORM 推导 role/data_scope/employee_id
              ↓
       contextvar 注入 MCPAuth（请求级隔离，无竞态）
              ↓
       execute_tool 覆写
          ├─ _check_table_access    表级准入
          ├─ handler 执行业务逻辑
          └─ _apply_auth            结果集脱敏
```

- **鉴权**：JWT（HS256）+ DB 实时 role 校验，拒绝 token 内嵌 role
- **隔离**：权限上下文通过 Python `contextvars` 传递，并发请求不串扰
- **覆盖**：核心工具 + 业务工具统一经 `execute_tool` 覆写脱敏，`execute_sql` 后门已补 RLS
- **fail-closed**：权限计算失败 → 拒绝查询，而非退回到无限制状态

### 角色

| 角色 | 数据范围 | 敏感字段 |
|------|----------|---------|
| `admin` | 全部 | 全部可见（原值） |
| `hr_director` | 部门及下属 | 全部可见（原值） |
| `finance_director` | 全部 | 财务相关可见 |
| `dept_ceo` / `dept_manager` | 团队 | 脱敏显示 salary/phone/email |
| `sales_manager` | 团队 | 联系方式脱敏 |
| `finance_bp` | 部门 | 财务相关可见 |
| `employee` | 仅自己 | 自己数据脱敏显示 salary/phone/email |
| `viewer` | 部门 | 基础信息，salary/phone/email 脱敏 |

> 所有非 `admin`/`hr_director` 角色访问 `salary`、`phone`、`email` 等敏感字段时，值自动脱敏（如 `138****8000`、`zh***@example.com`、`***`）。列可见性不受影响。

### 行级安全（RLS）

- **self_only** — `WHERE employee_id = 当前用户`
- **team** — `WHERE dept_id = 当前部门`
- **dept** — `WHERE dept_id IN (部门及子部门)`
- **all** — 无行级限制

RLS 条件通过 `apply_rls_filter` 自动注入 SQL，支持已有 `WHERE` 的 AND 追加和无 WHERE 的正确插入（ORDER BY / GROUP BY 之前）。

---

## API

### 核心接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 登录获取 JWT Token |
| `/api/query/ask` | POST | **统一查询入口**（委托 LangGraph Agent） |
| `/api/query/history` | GET | 查询历史 |
| `/api/agent/ask` | POST | Agent 多轮对话入口 |
| `/api/dashboard/panels` | GET | 仪表盘 KPI 面板 |
| `/api/datasources` | GET | 可用数据源列表（admin） |

### 请求示例

```bash
curl -X POST http://127.0.0.1:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "question": "各部门预算情况",
    "datasource_id": "<数据源 ID>"
  }'
```

---

## 测试

```bash
cd backend

# 运行全部测试
.venv\Scripts\python -m pytest tests/ -v

# 运行权限回归测试（推荐改动前后都跑）
.venv\Scripts\python -m pytest tests/test_mcp_auth_rls.py -v
```

测试覆盖：MCPAuth 权限矩阵（20 用例）、行级安全（20 用例）、Agent 编排、SQL 质量。
