# -*- coding: utf-8 -*-
"""DataMind Agent Multi-Role Comprehensive Test
Tests agent capabilities with different roles: admin, dept_manager, employee, viewer
Tests MCP tool flow through the complete pipeline
"""

import os, sys, json, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.mcp_servers.registry import init_mcp_servers, get_server
from app.mcp_servers.base_sql import MCPAuth
from app.mcp_client import get_mcp_client
from app.core.query_engine import parse_query_intent

os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))


# ============================================================
# Test Role Definitions
# ============================================================
TEST_USERS = {
    "admin": {
        "role": "admin",
        "data_scope": "all",
        "employee_id": None,
        "dept_id": None,
        "desc": "System admin - full access"
    },
    "hr_director": {
        "role": "hr_director",
        "data_scope": "all",
        "employee_id": 1,
        "dept_id": 1,
        "desc": "HR Director - can see sensitive HR data"
    },
    "dept_manager": {
        "role": "dept_manager",
        "data_scope": "dept",
        "employee_id": 1,
        "dept_id": 101,
        "desc": "Dept manager - can see own dept data"
    },
    "employee": {
        "role": "employee",
        "data_scope": "self_only",
        "employee_id": 5,
        "dept_id": 101,
        "desc": "Regular employee - can only see own data"
    },
    "viewer": {
        "role": "viewer",
        "data_scope": "dept",
        "employee_id": None,
        "dept_id": None,
        "desc": "Viewer - read-only with limited access"
    },
    "finance_director": {
        "role": "finance_director",
        "data_scope": "all",
        "employee_id": 10,
        "dept_id": 201,
        "desc": "Finance Director - full finance access"
    },
    "dept_ceo": {
        "role": "dept_ceo",
        "data_scope": "dept_and_sub",
        "employee_id": 1,
        "dept_id": 1,
        "desc": "Dept CEO - can see dept and sub-dept data"
    },
    "sales_manager_alt": {
        "role": "sales_manager",
        "data_scope": "dept",
        "employee_id": 15,
        "dept_id": 301,
        "desc": "Sales Manager - can see CRM data"
    },
        "finance_bp": {
        "role": "finance_bp",
        "data_scope": "dept",
        "employee_id": 10,
        "dept_id": 201,
        "desc": "Finance BP - can see finance data"
    },
    "sales_manager": {
        "role": "sales_manager",
        "data_scope": "dept",
        "employee_id": 15,
        "dept_id": 301,
        "desc": "Sales manager - can see CRM data"
    }
}


# ============================================================
# Test Scenario Definitions
# ============================================================
TEST_SCENARIOS = [
    # ---- HR Domain Tests ----
    {
        "id": "HR-01",
        "question": "Show me the org structure of the company",
        "domain": "hr",
        "expected_roles": ["admin", "hr_director", "dept_manager", "employee", "viewer"],
        "check": lambda r: r.get("success") and len(r.get("data",{}).get("departments",[])) > 0
    },
    {
        "id": "HR-02",
        "question": "How many employees are in each department?",
        "domain": "hr",
        "expected_roles": ["admin", "hr_director", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "HR-03",
        "question": "Show employee details for ID 3",
        "domain": "hr",
        "expected_roles": ["admin", "hr_director"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "HR-04",
        "question": "What is the performance ranking of employees?",
        "domain": "hr",
        "expected_roles": ["admin", "hr_director", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "HR-05",
        "question": "Show attendance summary for this month",
        "domain": "hr",
        "expected_roles": ["admin", "hr_director", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    
    # ---- CRM Domain Tests ----
    {
        "id": "CRM-01",
        "question": "Show me the customer distribution by industry",
        "domain": "crm",
        "expected_roles": ["admin", "sales_manager", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "CRM-02",
        "question": "What is the sales pipeline status?",
        "domain": "crm",
        "expected_roles": ["admin", "sales_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "CRM-03",
        "question": "Show deals with amount over 50000",
        "domain": "crm",
        "expected_roles": ["admin", "sales_manager"],
        "check": lambda r: r.get("success")
    },
    
    # ---- Finance Domain Tests ----
    {
        "id": "FIN-01",
        "question": "Show me the budget overview for this year",
        "domain": "finance",
        "expected_roles": ["admin", "finance_bp", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "FIN-02",
        "question": "Show expense summary by category",
        "domain": "finance",
        "expected_roles": ["admin", "finance_bp"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "FIN-03",
        "question": "What is the budget execution rate?",
        "domain": "finance",
        "expected_roles": ["admin", "finance_bp", "finance_director"],
        "check": lambda r: r.get("success")
    },
    
    # ---- ERP Domain Tests ----
    {
        "id": "ERP-01",
        "question": "Show me the project overview",
        "domain": "erp",
        "expected_roles": ["admin", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "ERP-02",
        "question": "What is the inventory status?",
        "domain": "erp",
        "expected_roles": ["admin", "dept_ceo", "dept_manager"],
        "check": lambda r: r.get("success")
    },
    {
        "id": "ERP-03",
        "question": "Show low stock alerts",
        "domain": "erp",
        "expected_roles": ["admin", "dept_ceo", "dept_manager"],
        "check": lambda r: r.get("success")
    },
]


class AgentTester:
    def __init__(self):
        init_mcp_servers()
        self.client = get_mcp_client()
        self.results = []
    
    def _set_auth(self, user_info):
        self.client.set_auth(
            user_role=user_info["role"],
            data_scope=user_info["data_scope"],
            employee_id=user_info.get("employee_id"),
            dept_id=user_info.get("dept_id"),
        )
    
    async def test_scenario(self, scenario, role_name, user_info):
        """Test a single scenario with a specific role"""
        self._set_auth(user_info)
        server = get_server(scenario["domain"])
        if not server:
            return {"success": False, "error": f"No server for {scenario['domain']}"}
        
        result = None
        
        # Try business-specific tools first
        tools = [t["function"]["name"] for t in server.list_tools()]
        
        # For each scenario, we try the most relevant tool
        question_lower = scenario["question"].lower()
        
        if "org structure" in question_lower or "org chart" in question_lower:
            result = await server.execute_tool("get_org_structure", {})
        elif "how many employees" in question_lower or "employee distribution" in question_lower:
            result = await server.execute_tool("get_employee_distribution", {"group_by": "dept_id"})
        elif "employee detail" in question_lower:
            result = await server.execute_tool("get_employee_detail", {"employee_id": 3})
        elif "performance ranking" in question_lower:
            result = await server.execute_tool("get_performance_ranking", {})
        elif "attendance summary" in question_lower:
            result = await server.execute_tool("get_attendance_summary", {})
        elif "customer distribution" in question_lower:
            result = await server.execute_tool("get_customer_distribution", {"group_by": "industry"})
        elif "sales pipeline" in question_lower or "pipeline" in question_lower:
            result = await server.execute_tool("get_sales_pipeline", {})
        elif "deals" in question_lower and "amount" in question_lower:
            result = await server.execute_tool("search_deals", {"min_amount": 50000, "limit": 10})
        elif "budget overview" in question_lower:
            result = await server.execute_tool("get_budget_overview", {})
        elif "expense summary" in question_lower:
            result = await server.execute_tool("get_expense_summary", {"group_by": "category"})
        elif "budget execution" in question_lower:
            result = await server.execute_tool("get_budget_execution_rate", {})
        elif "project overview" in question_lower or "project" in question_lower:
            result = await server.execute_tool("get_project_overview", {})
        elif "inventory status" in question_lower or "inventory" in question_lower:
            result = await server.execute_tool("get_inventory_status", {})
        elif "low stock" in question_lower:
            result = await server.execute_tool("get_low_stock_alerts", {})
        else:
            result = await server.execute_tool("query", {"main_table": "", "select_columns": [], "limit": 5})
        
        return {
            "success": result.success,
            "data": result.data if result.success else None,
            "error": result.error if not result.success else None,
        }
    
    async def run_all(self):
        """Run all test scenarios against all roles"""
        print("=" * 70)
        print("  DataMind Agent Multi-Role Comprehensive Test")
        print("=" * 70)
        
        total = 0
        passed = 0
        failed = 0
        
        for scenario in TEST_SCENARIOS:
            scenario_id = scenario["id"]
            question = scenario["question"]
            
            for role_name in scenario["expected_roles"]:
                user_info = TEST_USERS[role_name]
                total += 1
                
                try:
                    result = await self.test_scenario(scenario, role_name, user_info)
                    ok = scenario["check"](result)
                    
                    status = "PASS" if ok else "FAIL"
                    if ok: passed += 1
                    else: failed += 1
                    
                    detail = ""
                    if result.get("success"):
                        data = result.get("data", {})
                        if isinstance(data, dict):
                            keys = list(data.keys())[:3]
                            detail = f" keys={keys}"
                    else:
                        detail = f" error={result.get('error','')[:60]}"
                    
                    print(f"  [{status}] {scenario_id}/{role_name:15s} | {question[:40]:40s}{detail}")
                    
                except Exception as e:
                    failed += 1
                    print(f"  [FAIL] {scenario_id}/{role_name:15s} | {question[:40]:40s} exception={str(e)[:60]}")
        
        print()
        print("=" * 70)
        print(f"  TOTAL: {total}  PASS: {passed}  FAIL: {failed}")
        print(f"  PASS RATE: {passed*100//max(total,1)}%")
        print("=" * 70)
        
        return {"total": total, "passed": passed, "failed": failed}


async def main():
    tester = AgentTester()
    await tester.run_all()


if __name__ == "__main__":
    asyncio.run(main())
