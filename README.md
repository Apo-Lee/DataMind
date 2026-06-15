# DataMind V2

> 更新时间: 2026-06-13 | 版本: 0.2.0

DataMind 是一个面向企业白领的 AI 数据自助分析平台。管理员做一次 HR 系统同步，业务人员即可用自然语言查询和分析自己权限内的业务数据。

**V2 核心变革**: HR 系统作为组织架构数据锚点，系统用户自动从 HR 系统同步，实现基于组织架构的行级数据权限控制。

## 系统架构

```
HR 系统 (组织架构/人员数据锚点)
    ↓ 自动同步
DataMind 系统数据库 (用户 + 权限)
    ↓ 行级权限控制
CRM / 费控 / ERP (共享统一的 dept_id + employee_id)
    ↓
BI 驾驶舱 + 自然语言问答
```

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
| 其他用户 | `emp{工号}@{手机后4位}` | 按职位自动映射 | 按角色+组织架构 |

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

## 权限体系 (V2)

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

# 全部测试
uv run python -m pytest tests/ -v
# 期望: 31 passed (包含 21 个行级安全测试 + 4 个集成测试 + 6 个服务测试)

# 行级安全专项测试
uv run python -m pytest tests/test_row_level_security.py -v
```

## 视觉体系

| 元素 | 值 |
|------|-----|
| 侧边栏 | `#0B1120` 深空黑 + 靛紫导航 |
| 主背景 | `#F7F8FC` 冷灰白 |
| 主色调 | `#5B5FE3` 靛紫 |
| 数据高亮 | `#00C9A7` 薄荷青 |
| 警告 | `#F59E0B` 琥珀 |
| 危险 | `#F43F5E` 玫瑰红 |

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 (async) + DeepSeek API
- **前端**: Vue 3 + Vite + Element Plus + ECharts + Pinia
- **沙箱**: Docker 临时容器 (pandas/numpy/scipy/matplotlib)
- **元数据库**: SQLite (开发) / PostgreSQL 15 (生产)

## V2 相比 V1 的变化

- HR 系统作为组织架构数据锚点
- 系统用户从 HR 自动同步 (182 个同步用户)
- 行级权限控制: 上级看下级、部门隔离、跨部门授权
- 管理后台增强: 系统监控、审计日志、HR 同步、系统配置、数据权限分配
- 数据源管理改为只读展示 (4 个系统预置数据源)
- 移除手动添加/上传数据源功能
