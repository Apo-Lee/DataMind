# DataMind V3

> 更新时间: 2026-06-15 | 版本: 0.3.0

DataMind 是一个面向企业白领的 **AI 数据自助分析平台**。管理者做一次 HR 系统同步，业务人员即可用自然语言查询和分析自己权限内的业务数据。

**V3 核心改革**: 引入 **LangGraph 多 Agent 编排架构**，将自然语言问答拆分为意图识别 → SQL 生成 → 深度分析 → 报告组装的完整流水线，支持 15 类意图分类和智能上下文追踪。

---

## 系统架构

```
HR 系统 (组织架构/人员数据锚点)
     ↓ 自动同步
DataMind 系统数据库 (用户 + 权限)
     ↓ RLS 行级权限控制
CRM / 费控 / ERP (共享统一的 dept_id + employee_id)
     ↓
┌─────────────────────────────────────────────────┐
│              LangGraph Agent 流水线              │
│                                                   │
│  用户问题                                          │
│     ↓                                              │
│  ┌──────────────────┐                              │
│  │  Intent Node     │ ← 15 类意图分类              │
│  │  (意图路由器)     │   问候/直查/聚合/趋势/对比/   │
│  └────┬─────────────┘   异常/归因/预测/下钻/跨域   │
│       │ greeting/help     其他                     │
│       ▼                    ▼                       │
│  ┌──────────┐    ┌──────────────────┐              │
│  │ Report   │    │   SQL Node       │ ← 权限校验    │
│  │ (问候/   │    │   (安全查询引擎)  │ ← RLS 注入    │
│  │  帮助)   │    └───────┬──────────┘ ← 数据脱敏   │
│  └──────────┘           │                          │
│                 complex  │  其他                     │
│                    ▼     ▼                          │
│          ┌──────────────────┐                       │
│          │  Analysis Node   │ ← 沙箱深度分析         │
│          │  (分析节点)       │ ← LLM 洞察生成        │
│          └───────┬──────────┘                       │
│                  ▼                                  │
│          ┌──────────────────┐                       │
│          │  Report Node     │ ← 模板化报告           │
│          │  (报告组装)       │ ← 追问建议生成         │
│          └──────────────────┘                       │
│                                                   │
└─────────────────────────────────────────────────┘
     ↓
  BI 驾驶舱 + AI 问答
```

## Agent 能力详解

### 15 类意图分类

| 类别 | 意图 | 示例问题 |
|------|------|---------|
| **直查类** | `direct_query` | "技术部有多少人" |
| | `list_query` | "列出所有部门" |
| | `aggregation` | "平均出勤率是多少" |
| **分析类** | `trend` | "近 6 个月的销售趋势" |
| | `comparison` | "对比 A 和 B 部门" |
| | `ranking` | "绩效评分 Top 10" |
| | `distribution` | "员工的学历分布" |
| | `anomaly` | "哪些数据异常" |
| | `root_cause` | "为什么这个月下降了" |
| | `forecast` | "下季度预测" |
| **交互类** | `drill_down` | "具体看技术部" |
| | `refinement` | "改按月份统计" |
| | `cross_domain` | "和 CRM 数据对比" |
| **元类** | `greeting` | "你好" |
| | `help` | "你能做什么" |

### 友好错误处理

当 Agent 遇到问题时，不会抛出硬生生的异常，而是返回用户友好的中文消息：

| 错误类型 | 示例消息 |
|---------|---------|
| **权限不足** | 🔒 无权查看薪资数据 — 薪资信息属于高度敏感数据… |
| **意图不明** | 🤔 我没完全理解你的问题 — 试试问「技术部有多少员工」 |
| **查询无结果** | 🔍 查询完成，未找到匹配的记录 — 试试放宽筛选范围 |
| **SQL 语法** | 😅 查询语法有问题 — 请换个说法重新描述 |
| **执行超时** | ⏱️ 查询时间较长 — 建议加上时间或部门筛选 |

## 演示数据 (中型企业)

| 系统 | 数据规模 |
|------|---------|
| HR 系统 | 191 员工, 17 部门 (含父子层级), 24,440 考勤, 544 汇报路径 |
| CRM 系统 | 800 客户, 3,000 交易, 4,000 跟进, 212 销售目标 |
| 费控系统 | 181 预算, 3,000 费用, 600 差旅明细, 17 成本中心 |
| ERP 系统 | 20 项目, 250 资源, 500 库存, 300 采购订单 |

## 预置系统用户

| 用户名 | 密码 | 角色 | 数据范围 |
|--------|------|------|----------|
| `admin` | `admin123` | 管理员 | 全部 |
| 其他用户 | `emp{工号}@{手机后4位}` | 按职位自动映射 | 按角色/组织架构 |

## 快速启动

```bash
# 1. 生成演示数据库
cd DataMind
uv run python demo_data/seed_unified_v2.py

# 2. 启动后端 (自动种子并同步 HR 数据)
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. 启动前端
cd frontend
npx vite --host 127.0.0.1 --port 5173

# 4. 浏览器打开
# http://localhost:5173
```

## 权限体系 (V3)

### 角色映射

| 职位 | 系统角色 | 默认行级范围 |
|------|---------|-------------|
| 管理员 | admin | 全部 |
| 部门总监 | dept_ceo | 直属下级 |
| HR总监 | hr_director | 本部门及子部门 |
| 财务总监 | finance_director | 全部 (跨部门) |
| 财务人员 | finance_bp | 本部门 |
| 经理/主管 | dept_manager | 直属下级 |
| 区域销售经理 | sales_manager | 直属下级 |
| 普通员工 | employee | 仅自己 |

### 行级权限数据范围

| scope | 含义 |
|-------|------|
| self_only | 仅看到自己的数据 |
| team | 直属下级 + 自己 (默认) |
| dept | 本部门 (平级所有同事) |
| dept_and_sub | 本部门及所有子部门 |
| cross_dept | 跨部门 (由管理员额外配置) |
| all | 全公司 |

Admin 可在「运维管理 → 数据权限」中为任意用户调整 data_scope 和额外授权部门。

## 测试

```bash
cd backend

# 全部单元测试
uv run python -m pytest tests/ -v
# 期望: 42 passed (含 11 个 Agent 路由测试 + 21 个行级安全测试 + 4 个集成测试 + 6 个服务测试)

# Agent 编排专项测试
uv run python -m pytest tests/test_agent_orchestrator.py -v
# 验证 15 类意图路由、SQL 执行、分析节点、报告组装的全链路

# Agent 全流程端到端测试
uv run python e2e_full_test_v2.py
# 验证 admin / dept_ceo / dept_manager / employee 四个角色的权限 + SQL 可执行性

# 行级安全专项测试
uv run python -m pytest tests/test_row_level_security.py -v

# SQL 质量检查
uv run python -m pytest tests/test_sql_quality.py -v
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/ask` | 创建会话并发起一问 (LangGraph 全链路) |
| POST | `/api/agent/followup` | 追问 — 在已有会话上继续对话 |
| GET | `/api/agent/history/{session_id}` | 获取会话历史 |
| POST | `/api/query/ask` | 传统单轮查询 (非 Agent 模式) |
| GET | `/api/query/history` | 查询历史列表 |

## Agent 配置

```python
# backend/app/orchestrator/graph/builder.py
# 工作流节点:
#   intent_node  →  sql_node / report_node
#                   ↓
#        analysis_node  →  report_node  →  END

# 意图路由:
#   greeting/help     → 直接报告
#   root_cause/forecast/anomaly → SQL → 深度分析 → 报告
#   其他              → SQL → 报告
```

## 视觉体系

| 元素 | 值 |
|------|-----|
| 侧边栏 | `#0B1120` 深空黑 + 靛紫导航 |
| 主背景 | `#F7F8FC` 冷灰白 |
| 主色调 | `#5B5FE3` 靛紫 |
| 数据高亮 | `#00C9A7` 薄荷绿 |
| 警告 | `#F59E0B` 琥珀 |
| 危险 | `#F43F5E` 玫瑰红 |

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 (async) + DeepSeek API + LangGraph
- **前端**: Vue 3 + Vite + Element Plus + ECharts + Pinia
- **沙箱**: Docker 临时容器 (pandas/numpy/scipy/matplotlib)
- **元数据库**: SQLite (开发) / PostgreSQL 15 (生产)

## V3 相比 V2 的变化

- **LangGraph Agent 编排**: 意图识别 → SQL 生成 → 深度分析 → 报告组装的完整流水线
- **15 类意图分类**: 从简单的 direct_query 扩展到趋势、对比、异常、归因、预测等分析类意图
- **智能追问建议**: 基于数据特征 (时间列、分类列、异常值) + LLM 生成业务追问
- **友好错误处理**: 7 类错误的中文友好消息，带建议和追问
- **会话管理**: 多轮对话上下文追踪，支持追问和会话历史
- **多 Agent 协作**: intent_node / sql_node / analysis_node / report_node 独立分工
- **行级安全增强**: 薪资字段 `highly_sensitive` 级别、员工角色聚合限制、额外部门授权
