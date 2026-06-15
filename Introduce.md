# DataMind BI 驾驶舱 — 项目完整介绍

> 版本: 0.2.0 | 最后更新: 2026-06-15 | 状态: 开发中 (V2)

---

## 一、背景

传统企业数据分析面临三大困境：

1. **IT 瓶颈**: 业务人员需要等待 IT 部门写 SQL 或开发报表，一个简单问题可能等数天
2. **数据孤岛**: HR、CRM、费控、ERP 各系统数据分散，无统一查询入口
3. **权限风险**: 直接访问数据库容易越权，敏感数据（薪资、电话、邮箱）需要脱敏保护

DataMind 是一个面向企业白领的 AI 数据自助分析平台。管理员做一次 HR 系统同步，业务人员即可用自然语言查询和分析自己权限内的业务数据，实现零 IT 介入的数据源接入体验。

---

## 二、项目意义

### 2.1 解决的核心问题

- 消除 IT 瓶颈: 自然语言直接到结果，业务人员无需技术背景即可自助分析
- 打破数据孤岛: 统一 BI 驾驶舱整合 HR/CRM/费控/ERP，跨系统关联分析
- 确保数据安全: 行级权限 + 列级敏感字段脱敏 + 三层权限校验，零越权风险
- 降低沟通成本: 看板自动生成 + AI 问答，几分钟完成原本数天的报表需求

### 2.2  数据核心

HR 系统作为组织架构数据锚点，系统用户自动从 HR 表同步（182 个同步用户），基于组织层级实现精确的行级数据权限控制：上级看下级、部门隔离、跨部门授权。

### 2.3 零风险查询架构（三层）

1. A 层 Prompt 约束: 在 AI 提示词中注入权限上下文，约束 LLM 生成符合权限的 SQL
2. B 层 SQL 规则引擎: SQL 执行前校验敏感字段、数据范围、多语句攻击等
3. C 层 结构化意图引擎: LLM 不直接生成 SQL，而是输出结构化查询意图 JSON Schema，由 PermissionEngine 校验后由 SQLBuilder 模板化生成安全的 SQL

### 2.4 适用场景

- 部门负责人查看团队 KPI 和出勤情况
- HR 人员查询员工信息和绩效分布
- 财务人员分析预算和费用趋势
- 销售经理追踪客户成交和业绩目标
- 普通员工仅查看自己的考勤和绩效数据

---

## 三、技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端框架 | FastAPI Python 3.12 | 单体模块化架构，async/await |
| ORM | SQLAlchemy 2.0 async | 数据库统一方言 |
| AI 模型 | DeepSeek API | 结构化 JSON 输出 + 自然语言理解 |
| 前端框架 | Vue 3 + Vite + TypeScript | Composition API，Pinia 状态管理 |
| UI 组件 | Element Plus | 企业级组件库 |
| 图表 | ECharts | 看板图表 + 分析图表 |
| 认证 | JWT | PBKDF2-SHA256 密码哈希 |
| Python 沙箱 | Docker 临时容器 | 复杂分析代码隔离执行 |
| 开发数据库 | SQLite | demo 数据 + 系统元数据 |
| 生产数据库 | PostgreSQL 15 | 元数据存储 |
| Markdown 渲染 | marked + highlight.js | 报告渲染 |

---

## 四、系统架构

### 4.1 整体架构

```
用户 (浏览器)
    │
    ├── BI 驾驶舱 (Vue 3)
    ├── 管理后台 (Vue 3 + Element Plus)
    └── 自然语言问答
    │
    ▼ REST API
┌──────────────────────────────┐
│          FastAPI 后端         │
│  API 路由 → Agent 层 → Core  │
│  Models → Schemas → 数据源   │
└──────────────────────────────┘
    │
    ├── 系统数据库 (SQLite/PostgreSQL)
    │   用户 / 数据源 / 对话历史 / 审计日志
    │
    ├── HR 系统 (SQLite) — 191 员工，17 部门，24440 考勤
    ├── CRM 系统 (SQLite) — 800 客户，3000 交易
    ├── 费控系统 (SQLite) — 181 预算，3000 费用
    └── ERP 系统 (SQLite) — 20 项目，500 库存
```

### 4.2 数据流向

```
用户问题 → 意图识别 → 结构化意图(JSON) → PermissionEngine 权限校验
    ↓ 通过
SQLBuilder 模板化生成 SQL → 执行 → 结果脱敏 → Markdown 报告
    ↓ 复杂分析
Python 沙箱 (Docker) → 统计建模/图表 → 深度报告
```
![alt text](UI-1.png)

---

## 五、演示数据

| 系统 | 数据规模 | 文件 |
|---|---|---|
| HR 系统 | 191 员工，17 部门，24440 考勤，544 汇报路径 | demo_data/hr_demo.sqlite |
| CRM 系统 | 800 客户，3000 交易，4000 跟进，212 销售目标 | demo_data/crm_demo.sqlite |
| 费控系统 | 181 预算，3000 费用，600 差旅，17 成本中心 | demo_data/finance_demo.sqlite |
| ERP 系统 | 20 项目，250 资源，500 库存，300 采购订单 | demo_data/erp_demo.sqlite |

所有外部数据库共享统一的 dept_id (1-999) 和 employee_id (1-999)，支持跨库行级权限过滤。

### 组织架构

```
数据智能集团
├── 技术研发中心 (dept=1)
│   ├── 平台架构部(101)
│   ├── 产品研发部(102)
│   └── AI实验室(103)
├── 市场营销部 (dept=2)
│   ├── 品牌公关部(201)
│   └── 数字营销部(202)
├── 人力资源部 (dept=3)
├── 财务管理部 (dept=4)
├── 销售业务部 (dept=5)
│   ├── 华东大区(501)  华南大区(502)
│   ├── 华北大区(503)  西南大区(504)
├── 运营支持部 (dept=6)
│   ├── IT运维部(601)
│   └── 客户服务部(602)
```

---

## 六、权限体系

### 6.1 用户角色

| 用户名 | 密码 | 角色 | 显示名 | 数据范围 |
|---|---|---|---|---|
| admin | admin123 | admin 管理员 | 系统管理员 | all 全部数据 |
| emp1 | emp1@0001 | dept_ceo 部门CEO | 张伟 技术总监 | team 直属下级 |
| emp31 | emp31@0001 | hr_director HR总监 | 王静 | dept_and_sub 部门及子部门 |
| emp37 | emp37@0001 | finance_director 财务总监 | 赵刚 | all 全部 |
| emp45 | emp45@0001 | dept_ceo 部门CEO | 陈强 销售总监 | team 直属下级 |
| 其他 | emp{工号}@{手机后4位} | 按职位自动映射 | HR 同步 | 按角色+组织架构 |

### 6.2 角色数据范围

| scope | 含义 | 适用角色 |
|---|---|---|
| self_only | 仅看到自己的数据 | employee 普通员工 |
| team | 直属下级 + 自己 | dept_ceo，dept_manager，sales_manager |
| dept | 本部门平级同事 | finance_bp 财务人员 |
| dept_and_sub | 本部门及所有子部门 | hr_director HR总监 |
| cross_dept | 跨部门由管理员配置 | 特殊需求 |
| all | 全公司 | admin，finance_director |

### 6.3 敏感字段策略

| 级别 | 字段 | 可查看角色 |
|---|---|---|
| safe | name，dept_id，position，join_date，出勤等 | 所有角色 |
| sensitive | phone，email，budget | hr_director，finance_bp，admin 及以上 |
| highly_sensitive | salary | admin，hr_director 可查看原始值；其他显示 *** |

### 6.4 权限校验流程

```
用户请求
  │
  ├─ A层: Prompt 注入权限上下文
  │   ├─ 角色描述 + 数据范围
  │   ├─ 敏感字段保护规则
  │   └─ 防止全表扫描规则
  │
  ├─ B层: SQL 规则引擎校验
  │   ├─ 敏感字段查询检测
  │   ├─ 多语句/危险操作检测
  │   ├─ 非 SELECT 语句拦截
  │   └─ WHERE 条件必要性检查
  │
  └─ C层: 结构化查询意图引擎
      ├─ LLM 输出 JSON Schema 非原始 SQL
      ├─ PermissionEngine 校验列/聚合/过滤
      ├─ SQLBuilder 模板化生成安全 SQL
      └─ mask_sensitive_data 后置脱敏
```

---

## 七、项目结构详解

### 7.1 后端 (backend/)

```
backend/
├── main.py              # 后端入口
├── app/
│   ├── main.py          # FastAPI 初始化 + 路由注册
│   ├── config.py        # Pydantic Settings
│   ├── database.py      # SQLAlchemy async engine
│   ├── seed.py          # V2 种子脚本
│   ├── api/             # REST API 路由层
│   │   ├── auth.py      # JWT 登录/刷新/用户信息
│   │   ├── users.py     # 用户管理 (admin)
│   │   ├── datasources.py # 数据源 CRUD + 探测
│   │   ├── dashboard.py # BI 驾驶舱数据 (KPI + ECharts)
│   │   ├── query.py     # AI 问答 API 零风险查询入口
│   │   └── admin/       # 运维管理子路由
│   │       ├── monitor.py   # 系统监控
│   │       ├── audit_logs.py # 审计日志
│   │       ├── hr_sync.py   # HR 同步
│   │       ├── config.py    # 系统配置
│   │       └── permissions.py # 数据权限分配
│   ├── core/            # 横切能力层
│   │   ├── auth.py      # JWT 工具 + PBKDF2
│   │   ├── permissions.py # RBAC + 数据源访问控制
│   │   ├── query_engine.py # 零风险查询引擎
│   │   ├── row_level_security.py # RLS 行级安全
│   │   ├── query_rewriter.py # SQL 拦截注入器
│   │   ├── llm_client.py # DeepSeek API 客户端
│   │   ├── reporter.py  # Markdown 报告组装
│   │   ├── audit.py     # 审计日志写入
│   │   ├── encryption.py # AES 加密
│   │   ├── hr_sync.py   # HR 同步引擎
│   │   └── sandbox.py   # Docker 沙箱
│   ├── agents/          # Agent 层
│   │   ├── base.py      # DataSourceAgent 基类
│   │   ├── factory.py   # Agent 工厂
│   │   ├── intent.py    # 意图识别
│   │   ├── sql_agent.py # SQL 生成含权限校验
│   │   └── analysis_agent.py # Python 分析
│   ├── models/          # SQLAlchemy ORM
│   │   ├── user.py      # User + UserRole + DataScope
│   │   ├── datasource.py # DataSource + Permission
│   │   ├── conversation.py # Conversation + KpiPreference
│   │   ├── audit_log.py # AuditLog + HrSyncLog
│   │   ├── permission.py # RowLevelPolicy
│   │   └── system_config.py # SystemConfig
│   └── schemas/         # Pydantic 请求/响应
│       ├── auth.py / user.py / datasource.py
│       ├── dashboard.py / query.py
├── tests/
│   ├── test_row_level_security.py # RLS 测试
│   ├── test_integration.py
│   ├── test_services.py
│   └── test_auth.py
├── .env                 # DeepSeek API Key
└── Dockerfile
```

### 7.2 前端 (frontend/)

```
frontend/
├── src/
│   ├── main.ts          # Vue 应用入口
│   ├── App.vue
│   ├── router/index.ts  # 路由配置
│   ├── stores/
│   │   ├── auth.ts      # 认证状态 (Pinia)
│   │   └── dashboard.ts # 看板数据状态
│   ├── api/
│   │   ├── index.ts     # Axios 实例 + 拦截器
│   │   ├── auth.ts / query.ts / dashboard.ts / ...
│   ├── components/
│   │   ├── AppLayout.vue    # 侧边栏布局
│   │   ├── QueryInput.vue   # 问答输入框
│   │   ├── KpiCard.vue      # KPI 卡片
│   │   ├── MarkdownReport.vue # 报告渲染
│   │   └── PanelCard.vue    # 面板卡片
│   ├── views/
│   │   ├── Login.vue
│   │   ├── analyst/
│   │   │   ├── DashboardView.vue # BI 驾驶舱主页面
│   │   │   ├── PanelDetail.vue   # 详情图表页 ECharts
│   │   │   └── ReportView.vue    # 历史报告详情
│   │   └── dashboard/
│   │       ├── Overview.vue  # 系统概览
│   │       ├── DataSources.vue # 数据源管理
│   │       ├── Users.vue     # 用户管理
│   │       ├── Permissions.vue # 数据权限
│   │       ├── Monitor.vue   # 系统监控
│   │       ├── AuditLogs.vue # 审计日志
│   │       ├── HrSync.vue    # HR 同步
│   │       └── SystemConfig.vue # 系统配置
│   └── styles/global.css # 全局样式
└── vite.config.ts
```

---

## 八、数据模型 (系统数据库)

### 8.1 users — 用户表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(36) UUID | 主键 |
| username | String(50) | 登录名 admin/emp{工号} |
| hashed_password | String(255) | PBKDF2-SHA256 哈希 |
| display_name | String(100) | 显示名 |
| role | Enum 9种 | admin/hr_director/finance_bp/finance_director/dept_ceo/dept_manager/sales_manager/employee/viewer |
| is_active | Boolean | 是否启用 |
| employee_id | Integer | HR 员工 ID 唯一索引 |
| dept_id | Integer | 所属部门 ID |
| manager_id | Integer | 直属上级 ID |
| data_scope | Enum 6种 | self_only/team/dept/dept_and_sub/cross_dept/all |
| extra_dept_ids | Text JSON | 额外授权部门列表 |
| source | String | manual / hr_sync |
| hr_synced_at | DateTime | 最近 HR 同步时间 |

### 8.2 datasources — 数据源表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(36) UUID | 主键 |
| name | String(100) | 友好名称 |
| db_type | Enum 4种 | mysql/postgresql/sqlite/mssql |
| host | String(255) | 连接地址 |
| port | Integer | 端口 |
| db_name | String(100) | 数据库名 |
| username | String(100) | 连接账号 |
| password_encrypted | String(512) | AES 加密存储 |
| business_tag | String(50) | hr/crm/finance/erp |
| schema_summary | JSON | 表结构缓存探测结果 |
| is_system | Boolean | 系统预置不可删除 |
| is_active | Boolean | 是否启用 |

### 8.3 conversations — 对话历史表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(36) UUID | 主键 |
| user_id | String(36) FK | 提问用户 |
| datasource_id | String(36) FK | 查询数据源 |
| question | Text | 用户问题 |
| intent | String(50) | 识别意图 |
| analysis_depth | String(10) | simple/complex |
| sql_generated | Text | 生成的 SQL |
| result_data | JSON | 查询结果 |
| report_markdown | Text | Markdown 分析报告 |
| created_at | DateTime | 创建时间 |

### 8.4 其它表

- datasource_permissions: 数据源级授权 按角色/用户/部门
- row_level_policies: 行级安全策略 按字段+层级过滤
- audit_logs: 操作审计日志 登录/查询/权限变更
- hr_sync_logs: HR 同步历史记录
- system_configs: 系统 key-value 配置
- kpi_preferences: 用户 KPI 卡片偏好设置


## 九、HR Demo 数据库结构

### employees (191行)

| 字段 | 类型 | 主键 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | 员工ID |
| name | TEXT |  | 姓名 |
| dept_id | INTEGER |  | 所属部门 FK |
| position | TEXT |  | 职位 |
| level | TEXT |  | 职级 P5-P8 |
| status | TEXT |  | 在职/离职/试用期 |
| join_date | TEXT |  | 入职日期 |
| salary | REAL |  | 薪资 highly_sensitive |
| performance_score | REAL |  | 绩效评分 0-100 |
| phone | TEXT |  | 手机号 sensitive |
| email | TEXT |  | 邮箱 sensitive |
| manager_id | INTEGER |  | 直属上级ID |
| position_category | TEXT |  | 岗位类别 |
| gender | TEXT |  | 性别 |
| education | TEXT |  | 学历 |

### departments (17行)

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 部门ID |
| name | TEXT | 部门名称 |
| parent_dept_id | INTEGER | 上级部门ID |
| manager_name | TEXT | 部门负责人 |
| budget | REAL | 部门预算 sensitive |
| location | TEXT | 办公地点 |

### attendance (24440行)

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 主键 |
| employee_id | INTEGER | 员工ID |
| date | TEXT | 日期 |
| check_in | TEXT | 签到时间 |
| check_out | TEXT | 签退时间 |
| status | TEXT | 出勤/请假/迟到/缺勤 |

### org_hierarchy (544行)

| 字段 | 类型 | 说明 |
|---|---|---|
| ancestor_id | INTEGER PK | 祖先员工ID |
| descendant_id | INTEGER PK | 后代员工ID |
| depth | INTEGER | 层深度 0=自己 1=直属下级 |


## 十、API 端点一览

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | /api/auth/login | 登录 | 公开 |
| POST | /api/auth/refresh | 刷新Token | 公开 |
| GET | /api/auth/me | 当前用户信息 | 登录 |
| GET | /api/users | 用户列表 | admin |
| PUT | /api/users/{id} | 更新用户 | admin |
| GET | /api/datasources | 数据源列表 | admin |
| POST | /api/datasources | 创建数据源 | admin |
| POST | /api/datasources/{id}/probe | 探测表结构 | admin |
| GET | /api/dashboard/panels | BI驾驶舱数据 | 登录 |
| GET | /api/dashboard/panels/{id}/detail | 面板详情ECharts | 登录 |
| POST | /api/query/ask | AI问答查询 | 登录 |
| GET | /api/query/history | 问答历史 | 登录 |
| POST | /api/admin/hr-sync/trigger | HR同步触发 | admin |
| GET | /api/admin/monitor/stats | 系统监控统计 | admin |
| GET | /api/admin/audit-logs | 审计日志 | admin |
| PUT | /api/admin/permissions/users/{id} | 修改用户权限 | admin |
| GET | /api/health | 健康检查 | 公开 |


## 十一、BI 驾驶舱前端

### 界面布局

```
┌─────────────────────────────────────────────────────┐
│  Header: DataMind 品牌 | 推荐提问 | 用户信息      │
├────────────────────────────────┬────────────────────┤
│  主看板区 (60%)               │  副看板 (40%)      │
│  HR 系统 主看板               │  CRM 费控 ERP 卡片 │
│  KPI: 员工数/部门数/出勤率    │  点击切换为主看板  │
│  图表1: 各部门在职人数 柱状图 │                    │
│  图表2: 绩效分布 饼图         │                    │
│  图表3: 近6月考勤统计 堆叠柱  │                    │
├────────────────────────────────┴────────────────────┤
│  问我任何关于数据的问题...              [分析]     │
└─────────────────────────────────────────────────────┘
```

### HR 主看板图表说明 (3个)

1. 各部门在职人数 (柱状图): 统计所有部门在职员工数量，按人数降序排列
2. 绩效分布 (饼图): 按绩效评分分档 优秀90+/良好75-89/待改进60-74/不及格<60
3. 近6月考勤统计 (堆叠柱状图): 近6个月每月出勤/请假/迟到数量


## 十二、安全设计

| 层面 | 策略 |
|---|---|
| 认证 | JWT access 30min + refresh 7d，PBKDF2-SHA256 |
| 授权 | RBAC 角色到数据源权限，RLS 行级过滤 |
| SQL 注入 | 仅 SELECT + 参数化查询 + 自动 LIMIT |
| 零越权 | 结构化意图引擎 LLM不直接生成SQL |
| 数据源密码 | AES-256-CBC + HKDF 密钥派生 |
| Python沙箱 | Docker隔离 只读FS/无网络/资源限制 |
| 前端XSS | Markdown sanitize |
| 登录限速 | 滑动窗口 每IP 60秒5次 |
| 审计日志 | 所有关键操作记录 登录/查询/权限变更 |


## 十三、快速启动

```bash
# 1. 生成演示数据库
cd DataMind && python demo_data/seed_unified_v2.py

# 2. 启动后端 (自动种子 + HR同步)
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. 启动前端
cd frontend && npx vite --host 127.0.0.1 --port 5173

# 4. 浏览器打开 http://localhost:5173

# 测试账号:
# admin / admin123 (管理员，可看全部)
# emp1 / emp1@0001 (张伟，技术总监，部门CEO角色)
# emp31 / emp31@0001 (王静，HR总监)
```

