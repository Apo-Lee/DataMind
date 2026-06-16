"""
Finance MCP Server — 完整业务工具覆盖
费控: 预算、费用、差旅、成本中心
"""
import logging, pandas as pd
from sqlalchemy import text
from .base_sql import SQLMCPServer, MCPTool

logger = logging.getLogger(__name__)
DB_URL = "sqlite:///../demo_data/finance_demo.sqlite"

class FinanceMCPServer(SQLMCPServer):
    def __init__(self):
        super().__init__("费控系统", "finance", DB_URL)

    def _foreign_keys(self) -> dict:
        return {("expenses","departments"):("dept_id","id"),("travel_expenses","expenses"):("expense_id","id")}

    def _register_business_tools(self):
        # ─── 预算管理 ───
        self.register_tool(MCPTool(
            name="get_budget_overview",
            description="获取预算总览（按部门/年度/季度汇总预算总额、已使用、剩余）",
            parameters={
                "year": {"type": "integer", "description": "年份"},
                "quarter": {"type": "integer", "description": "季度"},
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
            },
        ), self._handle_budget_overview)

        self.register_tool(MCPTool(
            name="get_budget_detail",
            description="获取预算明细（按类别/预算类型查看预算分配和执行情况）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "year": {"type": "integer", "description": "年份"},
                "quarter": {"type": "integer", "description": "季度"},
                "category": {"type": "string", "description": "预算类别（办公费用/差旅费/设备采购等）"},
            },
        ), self._handle_budget_detail)

        self.register_tool(MCPTool(
            name="get_budget_execution_rate",
            description="获取预算执行率排名（按部门/类别对比预算使用率）",
            parameters={
                "year": {"type": "integer", "description": "年份"},
                "quarter": {"type": "integer", "description": "季度"},
            },
        ), self._handle_budget_execution_rate)

        # ─── 费用管理 ───
        self.register_tool(MCPTool(
            name="get_expense_summary",
            description="获取费用汇总（按类别/部门汇总金额，支持时间范围筛选）",
            parameters={
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "group_by": {
                    "type": "string",
                    "enum": ["category", "dept_id", "status", "expense_type"],
                    "description": "分组字段",
                },
            },
        ), self._handle_expense_summary)

        self.register_tool(MCPTool(
            name="search_expenses",
            description="搜索费用记录（按类别/状态/部门/金额范围/时间筛选）",
            parameters={
                "category": {"type": "string", "description": "费用类别"},
                "status": {"type": "string", "description": "审批状态（已审批/待审批/已驳回）"},
                "dept_id": {"type": "integer", "description": "部门ID"},
                "employee_id": {"type": "integer", "description": "申请人ID"},
                "min_amount": {"type": "number", "description": "最小金额"},
                "max_amount": {"type": "number", "description": "最大金额"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_search_expenses)

        self.register_tool(MCPTool(
            name="get_expense_trend",
            description="获取费用趋势（按月统计费用总额变化）",
            parameters={
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "category": {"type": "string", "description": "费用类别（可选）"},
            },
        ), self._handle_expense_trend)

        # ─── 差旅管理 ───
        self.register_tool(MCPTool(
            name="get_travel_expenses",
            description="获取差旅费用明细（按员工/目的地/时间筛选）",
            parameters={
                "employee_id": {"type": "integer", "description": "员工ID"},
                "destination": {"type": "string", "description": "目的地"},
                "start_date": {"type": "string", "description": "出发日期开始 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "返回日期结束 YYYY-MM-DD"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_travel_expenses)

        self.register_tool(MCPTool(
            name="get_travel_summary",
            description="获取差旅费用汇总（按目的地/员工汇总差旅总费用）",
            parameters={
                "group_by": {
                    "type": "string",
                    "enum": ["destination", "employee_id"],
                    "description": "分组字段",
                },
                "start_date": {"type": "string", "description": "出发日期开始 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "返回日期结束 YYYY-MM-DD"},
            },
        ), self._handle_travel_summary)

        # ─── 成本中心 ───
        self.register_tool(MCPTool(
            name="get_cost_centers",
            description="获取成本中心信息（按部门/年度查看预算总额和剩余）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "fiscal_year": {"type": "integer", "description": "财年"},
            },
        ), self._handle_cost_centers)

    # ═══════════════════════════════════════
    # 实现处理器
    # ═══════════════════════════════════════

    async def _handle_budget_overview(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("year"): where.append(f"year={int(args['year'])}")
        if args.get("quarter"): where.append(f"quarter={int(args['quarter'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT dept_id, year, quarter, SUM(amount) as total_budget, SUM(used) as total_used, SUM(remaining_adj) as total_remaining FROM budgets{w} GROUP BY dept_id, year, quarter ORDER BY year, quarter"
        df = pd.read_sql(text(sql), self._engine)
        return {"budget_overview": df.to_dict(orient="records")}

    async def _handle_budget_detail(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("year"): where.append(f"year={int(args['year'])}")
        if args.get("quarter"): where.append(f"quarter={int(args['quarter'])}")
        if args.get("category"): where.append(f"category='{args['category']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT * FROM budgets{w} ORDER BY year, quarter, dept_id, category"
        df = pd.read_sql(text(sql), self._engine)
        return {"budget_detail": df.to_dict(orient="records")}

    async def _handle_budget_execution_rate(self, args: dict) -> dict:
        where = []
        if args.get("year"): where.append(f"year={int(args['year'])}")
        if args.get("quarter"): where.append(f"quarter={int(args['quarter'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT dept_id, category, amount as budget, used, ROUND(used*100.0/amount,1) as execution_rate, remaining_adj as remaining FROM budgets{w} ORDER BY execution_rate DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"execution_rates": df.to_dict(orient="records")}

    async def _handle_expense_summary(self, args: dict) -> dict:
        where = []
        if args.get("start_date"): where.append(f"date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"date<='{args['end_date']}'")
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        gb = args.get("group_by", "category")
        sql = f"SELECT {gb}, COUNT(*) as count, SUM(amount) as total_amount, AVG(amount) as avg_amount FROM expenses{w} GROUP BY {gb} ORDER BY total_amount DESC"
        df = pd.read_sql(text(sql), self._engine)
        total = pd.read_sql(text(f"SELECT COUNT(*) as total_count, SUM(amount) as grand_total FROM expenses{w}"), self._engine)
        return {"expense_summary": df.to_dict(orient="records"), "total": total.to_dict(orient="records")}

    async def _handle_search_expenses(self, args: dict) -> dict:
        where = []
        if args.get("category"): where.append(f"category='{args['category']}'")
        if args.get("status"): where.append(f"status='{args['status']}'")
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("employee_id"): where.append(f"employee_id={int(args['employee_id'])}")
        if args.get("min_amount"): where.append(f"amount>={args['min_amount']}")
        if args.get("max_amount"): where.append(f"amount<={args['max_amount']}")
        if args.get("start_date"): where.append(f"date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        df = pd.read_sql(text(f"SELECT * FROM expenses{w} ORDER BY date DESC LIMIT {limit}"), self._engine)
        return {"expenses": df.to_dict(orient="records")}

    async def _handle_expense_trend(self, args: dict) -> dict:
        where = []
        if args.get("start_date"): where.append(f"date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"date<='{args['end_date']}'")
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("category"): where.append(f"category='{args['category']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT strftime('%Y-%m', date) as month, COUNT(*) as count, SUM(amount) as total FROM expenses{w} GROUP BY month ORDER BY month"
        df = pd.read_sql(text(sql), self._engine)
        return {"monthly_trend": df.to_dict(orient="records")}

    async def _handle_travel_expenses(self, args: dict) -> dict:
        where = []
        if args.get("employee_id"): where.append(f"t.employee_id={int(args['employee_id'])}")
        if args.get("destination"): where.append(f"t.destination='{args['destination']}'")
        if args.get("start_date"): where.append(f"t.departure_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"t.return_date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT t.*, e.amount as total_expense_amount, e.category, e.description FROM travel_expenses t LEFT JOIN expenses e ON t.expense_id=e.id{w} ORDER BY t.departure_date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"travel_expenses": df.to_dict(orient="records")}

    async def _handle_travel_summary(self, args: dict) -> dict:
        where = []
        if args.get("start_date"): where.append(f"departure_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"return_date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        gb = args.get("group_by", "destination")
        if gb == "destination":
            sql = f"SELECT destination, COUNT(*) as trip_count, SUM(transport_fee+hotel_fee+meal_fee+other_fee) as total_cost FROM travel_expenses{w} GROUP BY destination ORDER BY total_cost DESC"
        else:
            sql = f"SELECT employee_id, COUNT(*) as trip_count, SUM(transport_fee+hotel_fee+meal_fee+other_fee) as total_cost FROM travel_expenses{w} GROUP BY employee_id ORDER BY total_cost DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"travel_summary": df.to_dict(orient="records")}

    async def _handle_cost_centers(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("fiscal_year"): where.append(f"fiscal_year={int(args['fiscal_year'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT *, ROUND(budget_remaining*100.0/budget_total,1) as remaining_rate FROM cost_centers{w} ORDER BY fiscal_year DESC, dept_id"
        df = pd.read_sql(text(sql), self._engine)
        return {"cost_centers": df.to_dict(orient="records")}
