# -*- coding: utf-8 -*-
"""Repository 层单元测试

验证 5 个 Repository（Employee / Department / Customer / Finance / ERP）
的核心查询方法在可控数据下的正确性。

每个 Repo 使用独立的内存 SQLite 数据库 + 种子数据，
不依赖 demo_data/*.sqlite 外部文件。
"""
import pytest
from sqlalchemy import create_engine, text

from app.mcp_servers.repositories import (
    EmployeeRepository,
    DepartmentRepository,
    CustomerRepository,
    FinanceRepository,
    ErpRepository,
)


# ============================================================
# 辅助：在内存 SQLite 中创建表和种子数据
# ============================================================

_HR_DDL = {
    "departments": """
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY,
            name TEXT, budget REAL,
            manager_name TEXT, location TEXT,
            parent_dept_id INTEGER
        )
    """,
    "org_hierarchy": """
        CREATE TABLE org_hierarchy (
            id INTEGER PRIMARY KEY, dept_id INTEGER,
            parent_dept_id INTEGER, level INTEGER
        )
    """,
    "employees": """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER,
            position TEXT, level TEXT, status TEXT,
            join_date TEXT, performance_score REAL,
            salary REAL, phone TEXT, email TEXT,
            manager_id INTEGER, education TEXT, gender TEXT
        )
    """,
    "attendance": """
        CREATE TABLE attendance (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            date TEXT, status TEXT
        )
    """,
}


_CRM_DDL = {
    "customers": """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY, name TEXT,
            industry TEXT, level TEXT,
            contact_person TEXT, phone TEXT, email TEXT,
            created_date TEXT, owner_id INTEGER, owner_dept_id INTEGER
        )
    """,
    "deals": """
        CREATE TABLE deals (
            id INTEGER PRIMARY KEY, customer_id INTEGER,
            name TEXT, amount REAL, stage TEXT,
            status TEXT, owner_id INTEGER, dept_id INTEGER,
            created_date TEXT
        )
    """,
    "follow_ups": """
        CREATE TABLE follow_ups (
            id INTEGER PRIMARY KEY, customer_id INTEGER,
            employee_id INTEGER, type TEXT, date TEXT,
            content TEXT
        )
    """,
    "sales_targets": """
        CREATE TABLE sales_targets (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            dept_id INTEGER, year INTEGER, quarter INTEGER,
            target_amount REAL, achieved_amount REAL
        )
    """,
}

_FINANCE_DDL = {
    "budgets": """
        CREATE TABLE budgets (
            id INTEGER PRIMARY KEY, dept_id INTEGER,
            year INTEGER, quarter INTEGER,
            category TEXT, amount REAL,
            used REAL, remaining_adj REAL
        )
    """,
    "expenses": """
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY, dept_id INTEGER,
            employee_id INTEGER, category TEXT,
            amount REAL, date TEXT,
            status TEXT, description TEXT,
            expense_type TEXT
        )
    """,
    "travel_expenses": """
        CREATE TABLE travel_expenses (
            id INTEGER PRIMARY KEY, expense_id INTEGER,
            employee_id INTEGER,
            departure_date TEXT, return_date TEXT,
            destination TEXT, purpose TEXT,
            transport_fee REAL, hotel_fee REAL,
            meal_fee REAL, other_fee REAL
        )
    """,
    "cost_centers": """
        CREATE TABLE cost_centers (
            id INTEGER PRIMARY KEY, dept_id INTEGER,
            fiscal_year INTEGER, budget_total REAL,
            budget_remaining REAL
        )
    """,
}

_ERP_DDL = {
    "projects": """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY, name TEXT,
            project_code TEXT, status TEXT,
            priority TEXT, dept_id INTEGER,
            manager_id INTEGER, budget REAL,
            actual_cost REAL,
            start_date TEXT, end_date TEXT
        )
    """,
    "project_dept": """
        CREATE TABLE project_dept (
            id INTEGER PRIMARY KEY, project_id INTEGER,
            dept_id INTEGER
        )
    """,
    "resources": """
        CREATE TABLE resources (
            id INTEGER PRIMARY KEY, project_id INTEGER,
            employee_id INTEGER, role TEXT,
            daily_cost REAL
        )
    """,
    "inventory": """
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY, name TEXT,
            warehouse TEXT, category TEXT,
            quantity REAL, min_stock REAL,
            max_stock REAL, unit_price REAL,
            dept_id INTEGER
        )
    """,
    "purchase_orders": """
        CREATE TABLE purchase_orders (
            id INTEGER PRIMARY KEY, dept_id INTEGER,
            requester_id INTEGER, order_date TEXT,
            status TEXT, total_amount REAL
        )
    """,
}


def _create_engine(ddl: dict, seed: dict | None = None):
    """创建内存 SQLite + 建表 + 种子数据"""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    with eng.begin() as conn:
        for sql in ddl.values():
            conn.execute(text(sql))
        if seed:
            for table, rows in seed.items():
                for row in rows:
                    cols = ", ".join(f'"{c}"' for c in row.keys())
                    vals = ", ".join(f":{k}" for k in row.keys())
                    conn.execute(
                        text(f'INSERT INTO "{table}" ({cols}) VALUES ({vals})'),
                        row,
                    )
    return eng


# ============================================================
# HR Repo
# ============================================================

class TestEmployeeRepository:
    @pytest.fixture
    def repo(self):
        eng = _create_engine(
            _HR_DDL,
            {
                "departments": [
                    {"id": 1, "name": "技术部", "budget": 500000, "manager_name": "张三",
                     "location": "A栋", "parent_dept_id": None},
                ],
                "employees": [
                    {"id": 1, "name": "张三", "dept_id": 1, "position": "经理",
                     "level": "M3", "status": "在职", "join_date": "2023-01-01",
                     "performance_score": 95, "salary": 30000,
                     "phone": "13800001111", "email": "zhang@test.com",
                     "manager_id": None, "education": "本科", "gender": "M"},
                    {"id": 2, "name": "李四", "dept_id": 1, "position": "开发",
                     "level": "P4", "status": "在职", "join_date": "2024-06-01",
                     "performance_score": 85, "salary": 20000,
                     "phone": "13800002222", "email": "li@test.com",
                     "manager_id": 1, "education": "硕士", "gender": "M"},
                    {"id": 3, "name": "王五", "dept_id": 1, "position": "开发",
                     "level": "P5", "status": "离职", "join_date": "2022-01-01",
                     "performance_score": 0, "salary": 25000,
                     "phone": "13800003333", "email": "wang@test.com",
                     "manager_id": 1, "education": "本科", "gender": "F"},
                ],
                "attendance": [
                    {"id": 1, "employee_id": 1, "date": "2024-01-01", "status": "正常"},
                    {"id": 2, "employee_id": 1, "date": "2024-01-02", "status": "正常"},
                    {"id": 3, "employee_id": 2, "date": "2024-01-01", "status": "迟到"},
                ],
            },
        )
        return EmployeeRepository(eng)

    def test_get_by_id(self, repo):
        emp = repo.get_by_id(1)
        assert len(emp) == 1
        assert emp[0]["name"] == "张三"
        assert emp[0]["dept_name"] == "技术部"

    def test_search_by_keyword(self, repo):
        rows = repo.search(keyword="三")
        assert len(rows) >= 1
        assert rows[0]["name"] == "张三"

    def test_search_by_status(self, repo):
        rows = repo.search(status="离职")
        assert len(rows) == 1
        assert rows[0]["name"] == "王五"

    def test_count_by_dept(self, repo):
        rows = repo.count_by_dept()
        assert len(rows) == 1
        assert rows[0]["dept_id"] == 1
        assert rows[0]["cnt"] == 3

    def test_distribution(self, repo):
        rows = repo.distribution("gender")
        assert any(r["gender"] == "M" and r["count"] == 2 for r in rows)
        assert any(r["gender"] == "F" and r["count"] == 1 for r in rows)

    def test_performance_ranking(self, repo):
        rows = repo.performance_ranking(top_n=10)
        # 按 performance_score 降序排列，含离职（score=0 排在最后）
        assert len(rows) == 3
        assert rows[0]["name"] == "张三"
        assert rows[0]["performance_score"] == 95

    def test_attendance_summary(self, repo):
        rows = repo.attendance_summary(employee_id=1)
        assert len(rows) == 1  # 1 种状态
        assert rows[0]["days"] == 2

    def test_attendance_detail(self, repo):
        rows = repo.attendance_detail(employee_id=1)
        assert len(rows) == 2

    def test_attendance_trend(self, repo):
        rows = repo.attendance_trend()
        assert len(rows) == 3

    def test_new_hires(self, repo):
        rows = repo.new_hires(start_date="2024-01-01")
        assert len(rows) == 1
        assert rows[0]["name"] == "李四"

    def test_performance_overview(self, repo):
        result = repo.performance_overview()
        # 所有员工均参与统计（含离职，score=0）
        assert result["statistics"][0]["total"] == 3
        assert len(result["distribution"]) > 0

    def test_headcount_trend(self, repo):
        rows = repo.headcount_trend()
        assert len(rows) == 3  # 3 个员工分布在 3 个不同月份


class TestDepartmentRepository:
    @pytest.fixture
    def repo(self):
        eng = _create_engine(
            _HR_DDL,
            {
                "departments": [
                    {"id": 1, "name": "技术部", "budget": 500000,
                     "manager_name": "张三", "location": "A栋", "parent_dept_id": None},
                    {"id": 2, "name": "研发组", "budget": 300000,
                     "manager_name": "李四", "location": "A栋", "parent_dept_id": 1},
                ],
                "org_hierarchy": [
                    {"id": 1, "dept_id": 1, "parent_dept_id": None, "level": 0},
                    {"id": 2, "dept_id": 2, "parent_dept_id": 1, "level": 1},
                ],
                "employees": [
                    {"id": 1, "name": "张三", "dept_id": 1, "status": "在职",
                     **{k: "" for k in ["position","level","join_date",
                         "performance_score","salary","phone","email",
                         "manager_id","education","gender"]}},
                    {"id": 2, "name": "李四", "dept_id": 2, "status": "在职",
                     **{k: "" for k in ["position","level","join_date",
                         "performance_score","salary","phone","email",
                         "manager_id","education","gender"]}},
                ],
            },
        )
        return DepartmentRepository(eng)

    def test_org_structure(self, repo):
        result = repo.org_structure()
        assert len(result["departments"]) == 2
        assert len(result["hierarchy"]) == 2
        assert result["employee_counts"][0]["cnt"] == 1  # 在职

    def test_get_by_id(self, repo):
        dept = repo.get_by_id(1)
        assert len(dept) == 1
        assert dept[0]["name"] == "技术部"

    def test_members(self, repo):
        members = repo.members(1)
        assert len(members) == 1
        assert members[0]["name"] == "张三"

    def test_sub_departments(self, repo):
        subs = repo.sub_departments(1)
        assert len(subs) == 1
        assert subs[0]["name"] == "研发组"

    def test_budget_list(self, repo):
        rows = repo.budget_list()
        assert len(rows) == 2
        assert rows[0]["name"] == "技术部"  # 预算更高


# ============================================================
# CRM Repo
# ============================================================

class TestCustomerRepository:
    @pytest.fixture
    def repo(self):
        eng = _create_engine(
            _CRM_DDL,
            {
                "customers": [
                    {"id": 1, "name": "客户A", "industry": "科技",
                     "level": "A", "contact_person": "赵", "phone": "138",
                     "email": "a@t.com", "created_date": "2024-01-01",
                     "owner_id": 1, "owner_dept_id": 1},
                    {"id": 2, "name": "客户B", "industry": "金融",
                     "level": "B", "contact_person": "钱", "phone": "139",
                     "email": "b@f.com", "created_date": "2024-02-01",
                     "owner_id": 1, "owner_dept_id": 1},
                ],
                "deals": [
                    {"id": 1, "customer_id": 1, "name": "商机1",
                     "amount": 100000, "stage": "洽谈",
                     "status": "进行中", "owner_id": 1,
                     "dept_id": 1, "created_date": "2024-01-15"},
                    {"id": 2, "customer_id": 1, "name": "商机2",
                     "amount": 50000, "stage": "签约",
                     "status": "赢单", "owner_id": 1,
                     "dept_id": 1, "created_date": "2024-02-01"},
                ],
                "follow_ups": [
                    {"id": 1, "customer_id": 1, "employee_id": 1,
                     "type": "电话", "date": "2024-01-10", "content": "初步沟通"},
                ],
                "sales_targets": [
                    {"id": 1, "employee_id": 1, "dept_id": 1,
                     "year": 2024, "quarter": 1,
                     "target_amount": 200000, "achieved_amount": 150000},
                ],
            },
        )
        return CustomerRepository(eng)

    def test_search_customers(self, repo):
        rows = repo.search_customers(industry="科技")
        assert len(rows) == 1
        assert rows[0]["deal_count"] == 2

    def test_deals_by_customer(self, repo):
        deals = repo.deals_by_customer(1)
        assert len(deals) == 2

    def test_follow_ups_by_customer(self, repo):
        fups = repo.follow_ups_by_customer(1)
        assert len(fups) == 1

    def test_distribution(self, repo):
        rows = repo.distribution("industry")
        assert len(rows) == 2
        assert rows[0]["count"] >= 1

    def test_sales_pipeline(self, repo):
        pipe = repo.sales_pipeline()
        assert len(pipe) == 2  # 2 stages

    def test_search_deals(self, repo):
        deals = repo.search_deals(status="赢单")
        assert len(deals) == 1
        assert deals[0]["customer_name"] == "客户A"

    def test_deal_summary(self, repo):
        result = repo.deal_summary()
        assert result["overview"][0]["total"] == 2
        assert result["won"][0]["won_count"] == 1

    def test_deal_performance_ranking(self, repo):
        rows = repo.deal_performance_ranking()
        assert len(rows) == 1
        assert rows[0]["total_amount"] == 150000

    def test_sales_targets(self, repo):
        rows = repo.sales_targets(year=2024)
        assert len(rows) == 1
        assert "achievement_rate" in rows[0]


# ============================================================
# Finance Repo
# ============================================================

class TestFinanceRepository:
    @pytest.fixture
    def repo(self):
        eng = _create_engine(
            _FINANCE_DDL,
            {
                "budgets": [
                    {"id": 1, "dept_id": 1, "year": 2024, "quarter": 1,
                     "category": "办公费用", "amount": 50000,
                     "used": 30000, "remaining_adj": 20000},
                ],
                "expenses": [
                    {"id": 1, "dept_id": 1, "employee_id": 1,
                     "category": "办公费用", "amount": 5000,
                     "date": "2024-01-15", "status": "已审批",
                     "description": "购买文具", "expense_type": "日常"},
                ],
                "cost_centers": [
                    {"id": 1, "dept_id": 1, "fiscal_year": 2024,
                     "budget_total": 100000, "budget_remaining": 40000},
                ],
            },
        )
        return FinanceRepository(eng)

    def test_budget_overview(self, repo):
        rows = repo.budget_overview(year=2024)
        assert len(rows) == 1
        assert rows[0]["total_budget"] == 50000

    def test_expense_summary(self, repo):
        result = repo.expense_summary()
        assert result["expense_summary"][0]["total_amount"] == 5000
        assert result["total"][0]["grand_total"] == 5000

    def test_cost_centers(self, repo):
        rows = repo.cost_centers(fiscal_year=2024)
        assert len(rows) == 1
        assert "remaining_rate" in rows[0]


# ============================================================
# ERP Repo
# ============================================================

class TestErpRepository:
    @pytest.fixture
    def repo(self):
        eng = _create_engine(
            _ERP_DDL,
            {
                "projects": [
                    {"id": 1, "name": "项目Alpha", "project_code": "PA-001",
                     "status": "进行中", "priority": "P0",
                     "dept_id": 1, "manager_id": 1,
                     "budget": 1000000, "actual_cost": 600000,
                     "start_date": "2024-01-01", "end_date": "2024-12-31"},
                ],
                "resources": [
                    {"id": 1, "project_id": 1, "employee_id": 1,
                     "role": "后端开发", "daily_cost": 2000},
                ],
                "inventory": [
                    {"id": 1, "name": "显示器", "warehouse": "主仓",
                     "category": "电子设备", "quantity": 10,
                     "min_stock": 5, "max_stock": 50,
                     "unit_price": 3000, "dept_id": 1},
                ],
                "purchase_orders": [
                    {"id": 1, "dept_id": 1, "requester_id": 1,
                     "order_date": "2024-01-10", "status": "已到货",
                     "total_amount": 30000},
                ],
            },
        )
        return ErpRepository(eng)

    def test_project_overview(self, repo):
        result = repo.project_overview()
        assert result["by_status"][0]["count"] == 1
        assert result["total"][0]["total_budget"] == 1000000

    def test_search_projects(self, repo):
        rows = repo.search_projects(status="进行中")
        assert len(rows) == 1

    def test_project_budget_analysis(self, repo):
        rows = repo.project_budget_analysis()
        assert len(rows) == 1
        assert "cost_rate" in rows[0]

    def test_resource_allocation(self, repo):
        rows = repo.resource_allocation()
        assert len(rows) == 1
        assert rows[0]["project_name"] == "项目Alpha"

    def test_inventory_status(self, repo):
        rows = repo.inventory_status(low_stock_only=False)
        assert len(rows) == 1
        assert "stock_status" in rows[0]

    def test_inventory_summary(self, repo):
        rows = repo.inventory_summary(group_by="warehouse")
        assert len(rows) == 1
        assert rows[0]["item_count"] == 1

    def test_low_stock_alerts(self, repo):
        result = repo.low_stock_alerts()
        assert result["total_alerts"] == 0  # 10 > min_stock=5

    def test_search_purchase_orders(self, repo):
        rows = repo.search_purchase_orders(status="已到货")
        assert len(rows) == 1

    def test_purchase_summary(self, repo):
        rows = repo.purchase_summary()
        assert len(rows) == 1
