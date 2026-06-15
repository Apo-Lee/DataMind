# DataMind V2 系统数据模型

> 更新时间: 2026-06-13 | 版本: 0.2.0

## 组织架构

```
数据智能集团
├── 技术研发中心 (dept=1) → 平台架构部(101) / 产品研发部(102) / AI实验室(103)
├── 市场营销部   (dept=2) → 品牌公关部(201) / 数字营销部(202)
├── 人力资源部   (dept=3)
├── 财务管理部   (dept=4)
├── 销售业务部   (dept=5) → 华东(501)/华南(502)/华北(503)/西南(504) 大区
└── 运营支持部   (dept=6) → IT运维部(601) / 客户服务部(602)
```

## 系统用户

系统用户由 HR 同步自动创建，按职位智能化映射角色和权限。

| 用户名 | 密码 | 显示名 | 角色 | 部门 | 数据范围 |
|--------|------|--------|------|------|----------|
| `admin` | `admin123` | 系统管理员 | admin | - | all |
| `emp1` | `emp1@0001` | 张伟 | dept_ceo | 技术研发中心(1) | team |
| `emp31` | `emp31@0001` | 王静 | hr_director | 人力资源部(3) | dept_and_sub |
| `emp37` | `emp37@0001` | 赵刚 | finance_director | 财务管理部(4) | all |
| `emp45` | `emp45@0001` | 陈强 | dept_ceo | 销售业务部(5) | team |
| ... | ... | ... | (182个HR同步用户) | ... | ... |

## 外部数据源 (4个)

| 名称 | 标签 | 文件 | 数据规模 |
|------|------|------|---------|
| HR 系统 | hr | hr_demo.sqlite | 17部门, 191员工, 24,440考勤, 544汇报路径 |
| CRM 系统 | crm | crm_demo.sqlite | 800客户, 3,000交易, 4,000跟进, 212销售目标 |
| 费控系统 | finance | finance_demo.sqlite | 181预算, 3,000费用, 600差旅明细, 17成本中心 |
| ERP 系统 | erp | erp_demo.sqlite | 20项目, 250资源, 500库存, 300采购订单 |

## 跨系统关联

所有外部数据库共享统一的 dept_id (1-999) 和 employee_id (1-999)，支持跨库行级权限过滤和关联查询。

## 权限模型 (V2)

### 数据源权限 (DataSourcePermission)
- grant_type: role / user / dept — 按角色/用户/部门授权
- row_filter_scope: 覆盖用户默认 data_scope (可选)

### 行级权限 (RowLevelPolicy)
- 按数据源配置 dept_filter / employee_filter / custom_sql 策略
- 每次 SQL 执行前自动注入 WHERE 过滤条件

### 角色默认映射

| 角色 | 默认数据源 | 默认行级范围 |
|------|-----------|-------------|
| admin | hr/crm/finance/erp | all |
| hr_director | hr | dept_and_sub |
| finance_director | finance/hr | all |
| finance_bp | finance | dept |
| dept_ceo | hr/crm/finance/erp | team |
| dept_manager | hr/crm/finance/erp | team |
| sales_manager | crm/erp | team |
| employee | 按需 | self_only |

### 权限计算引擎

```
RowLevelSecurityEngine(user, datasource, db)
  ├── admin / data_scope=all → mode="all" (全量)
  ├── team → 直属下级 (org_hierarchy depth<=1)
  ├── dept → 本部门
  ├── dept_and_sub → 本部门 + 递归子部门
  ├── self_only → 仅自己
  └── + extra_dept_ids → 额外授权部门
```

## 启动

```bash
# 后端
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端
cd frontend && npx vite --host 127.0.0.1 --port 5173

# 浏览器
http://localhost:5173
```
