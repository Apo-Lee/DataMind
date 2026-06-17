# -*- coding: utf-8 -*-
"""查询引擎 — 敏感度映射常量定义（供 base_sql.MCPAuth 使用）

注意：原有的 parse_query_intent / PermissionEngine / SQLBuilder / mcp_safe_query / safe_query
等函数已在阶段2重构中移除（统一到 LangGraph OrchestratorAgent）。
"""

_COLUMN_SENSITIVITY = {
    "hr": {
        "employees": {
            "salary": "sensitive", "phone": "sensitive", "email": "sensitive",
            "name": "safe", "dept_id": "safe", "position": "safe",
            "level": "safe", "status": "safe", "join_date": "safe",
            "performance_score": "safe", "manager_id": "safe",
            "position_category": "safe", "gender": "safe", "education": "safe",
            "id": "safe",
        },
        "departments": {
            "budget": "sensitive", "name": "safe", "manager_name": "safe",
            "location": "safe", "parent_dept_id": "safe", "id": "safe",
        },
        "attendance": {
            "check_in": "safe", "check_out": "safe", "status": "safe",
            "date": "safe", "employee_id": "safe", "id": "safe",
        },
        "org_hierarchy": {"ancestor_id": "safe", "descendant_id": "safe", "depth": "safe"},
    },
    "crm": {
        "customers": {
            "phone": "sensitive", "email": "sensitive",
            "name": "safe", "industry": "safe", "level": "safe",
            "contact_person": "safe", "created_date": "safe",
            "owner_id": "safe", "owner_dept_id": "safe", "id": "safe",
        },
        "deals": {
            "amount": "safe", "status": "safe", "close_date": "safe",
            "probability": "safe", "title": "safe", "customer_id": "safe",
            "stage": "safe", "created_date": "safe",
            "expected_close_date": "safe", "owner_id": "safe",
            "dept_id": "safe", "id": "safe",
        },
        "follow_ups": {
            "type": "safe", "content": "safe", "next_action": "safe",
            "date": "safe", "customer_id": "safe", "employee_id": "safe",
            "id": "safe",
        },
        "sales_targets": {
            "target_amount": "safe", "achieved_amount": "safe",
            "year": "safe", "quarter": "safe",
            "employee_id": "safe", "dept_id": "safe", "id": "safe",
        },
    },
    "finance": {
        "expenses": {
            "amount": "safe", "category": "safe", "date": "safe",
            "status": "safe", "description": "safe", "dept_id": "safe",
            "employee_id": "safe", "approver_id": "safe",
            "expense_type": "safe", "project_code": "safe", "id": "safe",
        },
        "budgets": {
            "amount": "safe", "used": "safe", "remaining_adj": "safe",
            "year": "safe", "quarter": "safe", "category": "safe",
            "budget_type": "safe", "dept_id": "safe",
            "approver_id": "safe", "id": "safe",
        },
        "cost_centers": {"name": "safe", "budget_total": "safe", "budget_remaining": "safe", "fiscal_year": "safe", "dept_id": "safe", "id": "safe"},
        "travel_expenses": {"departure_date": "safe", "return_date": "safe", "destination": "safe", "purpose": "safe", "transport_fee": "safe", "hotel_fee": "safe", "meal_fee": "safe", "other_fee": "safe", "expense_id": "safe", "employee_id": "safe", "id": "safe"},
    },
    "erp": {
        "inventory": {"item_code": "safe", "name": "safe", "category": "safe", "quantity": "safe", "unit_price": "safe", "warehouse": "safe", "dept_id": "safe", "min_stock": "safe", "max_stock": "safe", "supplier_name": "safe", "id": "safe"},
        "projects": {"name": "safe", "project_code": "safe", "status": "safe", "budget": "safe", "actual_cost": "safe", "start_date": "safe", "end_date": "safe", "priority": "safe", "dept_id": "safe", "manager_id": "safe", "id": "safe"},
        "project_dept": {"project_id": "safe", "dept_id": "safe", "role": "safe", "id": "safe"},
        "purchase_orders": {"item_name": "safe", "quantity": "safe", "unit_price": "safe", "total_amount": "safe", "status": "safe", "order_date": "safe", "expected_date": "safe", "dept_id": "safe", "requester_id": "safe", "approver_id": "safe", "id": "safe"},
        "resources": {"project_id": "safe", "employee_id": "safe", "role": "safe", "allocation_pct": "safe", "daily_cost": "safe", "start_date": "safe", "end_date": "safe", "id": "safe"},
    },
}

_ROLE_SENSITIVITY_ACCESS = {
    "admin": {"safe", "sensitive", "highly_sensitive"},
    "hr_director": {"safe", "sensitive", "highly_sensitive"},
    "finance_bp": {"safe", "sensitive"}, "finance_director": {"safe", "sensitive"},
    "dept_ceo": {"safe", "sensitive"}, "dept_manager": {"safe", "sensitive"},
    "sales_manager": {"safe", "sensitive"},
    "employee": {"safe", "sensitive"}, "viewer": {"safe"},
}

