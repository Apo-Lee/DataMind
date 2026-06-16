"""
ERP MCP Server — 完整业务工具覆盖
企业资源: 项目、资源、库存、采购
"""
import logging, pandas as pd
from sqlalchemy import text
from .base_sql import SQLMCPServer, MCPTool

logger = logging.getLogger(__name__)
DB_URL = "sqlite:///../demo_data/erp_demo.sqlite"

class ERPMCPServer(SQLMCPServer):
    def __init__(self):
        super().__init__("ERP系统", "erp", DB_URL)

    def _foreign_keys(self) -> dict:
        return {("projects","departments"):("dept_id","id"),("resources","projects"):("project_id","id"),("purchase_orders","departments"):("dept_id","id")}

    def _register_business_tools(self):
        # ─── 项目管理 ───
        self.register_tool(MCPTool(
            name="get_project_overview",
            description="获取项目总览（按状态/优先级汇总项目数量和预算）",
            parameters={},
        ), self._handle_project_overview)

        self.register_tool(MCPTool(
            name="search_projects",
            description="搜索项目（按状态/优先级/部门/时间范围筛选）",
            parameters={
                "status": {"type": "string", "description": "状态（进行中/已完成/已暂停/规划中）"},
                "priority": {"type": "string", "description": "优先级（P0/P1/P2）"},
                "dept_id": {"type": "integer", "description": "负责部门ID"},
                "manager_id": {"type": "integer", "description": "项目经理ID"},
                "keyword": {"type": "string", "description": "项目名称关键词"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_search_projects)

        self.register_tool(MCPTool(
            name="get_project_detail",
            description="获取单个项目详细信息（含项目信息、参与部门、资源分配）",
            parameters={"project_id": {"type": "integer", "description": "项目ID"}},
            required=["project_id"],
        ), self._handle_project_detail)

        self.register_tool(MCPTool(
            name="get_project_budget_analysis",
            description="获取项目预算分析（预算 vs 实际成本 vs 偏差率）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
            },
        ), self._handle_project_budget_analysis)

        self.register_tool(MCPTool(
            name="get_project_timeline",
            description="获取项目时间线（按开始/结束日期排序的项目列表）",
            parameters={
                "status": {"type": "string", "description": "状态筛选"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_project_timeline)

        # ─── 资源管理 ───
        self.register_tool(MCPTool(
            name="get_resource_allocation",
            description="获取资源分配情况（按项目汇总人力/角色/成本）",
            parameters={
                "project_id": {"type": "integer", "description": "项目ID（可选）"},
                "employee_id": {"type": "integer", "description": "员工ID（可选）"},
            },
        ), self._handle_resource_allocation)

        self.register_tool(MCPTool(
            name="get_resource_cost_analysis",
            description="获取资源成本分析（按项目/角色汇总人力成本）",
            parameters={
                "project_id": {"type": "integer", "description": "项目ID（可选）"},
            },
        ), self._handle_resource_cost_analysis)

        # ─── 库存管理 ───
        self.register_tool(MCPTool(
            name="get_inventory_status",
            description="获取库存状态（可按仓库/类别筛选，支持低库存预警）",
            parameters={
                "warehouse": {"type": "string", "description": "仓库名（可选）"},
                "category": {"type": "string", "description": "商品类别"},
                "low_stock_only": {"type": "boolean", "description": "仅显示低库存商品（库存<=最低库存）"},
                "keyword": {"type": "string", "description": "商品名称关键词"},
                "limit": {"type": "integer", "default": 100},
            },
        ), self._handle_inventory_status)

        self.register_tool(MCPTool(
            name="get_inventory_summary",
            description="获取库存汇总（按仓库/类别汇总数量和金额）",
            parameters={
                "group_by": {"type": "string", "enum": ["warehouse", "category"], "description": "分组字段"},
            },
        ), self._handle_inventory_summary)

        self.register_tool(MCPTool(
            name="get_low_stock_alerts",
            description="获取低库存预警列表（库存量低于最低库存线的商品）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
            },
        ), self._handle_low_stock_alerts)

        # ─── 采购管理 ───
        self.register_tool(MCPTool(
            name="search_purchase_orders",
            description="搜索采购单（按状态/部门/时间范围筛选）",
            parameters={
                "status": {"type": "string", "description": "状态（已下单/已到货/已取消）"},
                "dept_id": {"type": "integer", "description": "采购部门ID"},
                "requester_id": {"type": "integer", "description": "申请人ID"},
                "start_date": {"type": "string", "description": "下单日期开始 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "下单日期结束 YYYY-MM-DD"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_search_purchase_orders)

        self.register_tool(MCPTool(
            name="get_purchase_summary",
            description="获取采购汇总（按部门/状态汇总采购金额）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
            },
        ), self._handle_purchase_summary)

    # ═══════════════════════════════════════
    # 实现处理器
    # ═══════════════════════════════════════

    async def _handle_project_overview(self, args: dict) -> dict:
        by_status = pd.read_sql(text("SELECT status, COUNT(*) as count, SUM(budget) as total_budget, SUM(actual_cost) as total_cost FROM projects GROUP BY status"), self._engine)
        by_priority = pd.read_sql(text("SELECT priority, COUNT(*) as count FROM projects GROUP BY priority ORDER BY priority"), self._engine)
        total = pd.read_sql(text("SELECT COUNT(*) as total, SUM(budget) as total_budget, SUM(actual_cost) as total_cost FROM projects"), self._engine)
        return {"by_status": by_status.to_dict(orient="records"), "by_priority": by_priority.to_dict(orient="records"), "total": total.to_dict(orient="records")}

    async def _handle_search_projects(self, args: dict) -> dict:
        where = []
        if args.get("status"): where.append(f"status='{args['status']}'")
        if args.get("priority"): where.append(f"priority='{args['priority']}'")
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("manager_id"): where.append(f"manager_id={int(args['manager_id'])}")
        if args.get("keyword"): where.append(f"name LIKE '%{args['keyword']}%'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT * FROM projects{w} ORDER BY start_date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"projects": df.to_dict(orient="records")}

    async def _handle_project_detail(self, args: dict) -> dict:
        pid = int(args["project_id"])
        proj = pd.read_sql(text(f"SELECT * FROM projects WHERE id={pid}"), self._engine)
        depts = pd.read_sql(text(f"SELECT * FROM project_dept WHERE project_id={pid}"), self._engine)
        resources = pd.read_sql(text(f"SELECT * FROM resources WHERE project_id={pid}"), self._engine)
        return {"project": proj.to_dict(orient="records"), "participating_depts": depts.to_dict(orient="records"), "resources": resources.to_dict(orient="records")}

    async def _handle_project_budget_analysis(self, args: dict) -> dict:
        where = f" WHERE dept_id={int(args['dept_id'])}" if args.get("dept_id") else ""
        sql = f"SELECT id, name, project_code, status, budget, actual_cost, ROUND(actual_cost*100.0/budget,1) as cost_rate, (budget-actual_cost) as remaining FROM projects{where} ORDER BY cost_rate DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"budget_analysis": df.to_dict(orient="records")}

    async def _handle_project_timeline(self, args: dict) -> dict:
        where = f" WHERE status='{args['status']}'" if args.get("status") else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT id, name, project_code, status, start_date, end_date, priority FROM projects{where} ORDER BY start_date LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"timeline": df.to_dict(orient="records")}

    async def _handle_resource_allocation(self, args: dict) -> dict:
        where = []
        if args.get("project_id"): where.append(f"r.project_id={int(args['project_id'])}")
        if args.get("employee_id"): where.append(f"r.employee_id={int(args['employee_id'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT r.*, p.name as project_name, p.status as project_status FROM resources r LEFT JOIN projects p ON r.project_id=p.id{w} ORDER BY r.project_id, r.role"
        df = pd.read_sql(text(sql), self._engine)
        return {"resources": df.to_dict(orient="records")}

    async def _handle_resource_cost_analysis(self, args: dict) -> dict:
        where = f" WHERE project_id={int(args['project_id'])}" if args.get("project_id") else ""
        sql = f"SELECT project_id, role, COUNT(*) as headcount, SUM(daily_cost) as total_daily_cost FROM resources{where} GROUP BY project_id, role ORDER BY project_id, total_daily_cost DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"cost_analysis": df.to_dict(orient="records")}

    async def _handle_inventory_status(self, args: dict) -> dict:
        where = []
        if args.get("warehouse"): where.append(f"warehouse='{args['warehouse']}'")
        if args.get("category"): where.append(f"category='{args['category']}'")
        if args.get("keyword"): where.append(f"name LIKE '%{args['keyword']}%'")
        if args.get("low_stock_only"): where.append("quantity <= min_stock")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT *, (quantity*unit_price) as total_value, (quantity - min_stock) as stock_above_min, CASE WHEN quantity <= min_stock THEN '预警' WHEN quantity <= max_stock*0.3 THEN '偏低' ELSE '正常' END as stock_status FROM inventory{w} ORDER BY stock_status, category, name LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"inventory": df.to_dict(orient="records")}

    async def _handle_inventory_summary(self, args: dict) -> dict:
        gb = args.get("group_by", "warehouse")
        sql = f"SELECT {gb}, COUNT(*) as item_count, SUM(quantity) as total_quantity, SUM(quantity*unit_price) as total_value, SUM(CASE WHEN quantity<=min_stock THEN 1 ELSE 0 END) as low_stock_count FROM inventory GROUP BY {gb}"
        df = pd.read_sql(text(sql), self._engine)
        return {"inventory_summary": df.to_dict(orient="records")}

    async def _handle_low_stock_alerts(self, args: dict) -> dict:
        where = f" WHERE dept_id={int(args['dept_id'])}" if args.get("dept_id") else ""
        sql = f"SELECT *, (quantity*unit_price) as total_value, (min_stock - quantity) as shortage FROM inventory{where} AND quantity <= min_stock ORDER BY shortage DESC" if where else "SELECT *, (quantity*unit_price) as total_value, (min_stock - quantity) as shortage FROM inventory WHERE quantity <= min_stock ORDER BY shortage DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"alerts": df.to_dict(orient="records"), "total_alerts": len(df)}

    async def _handle_search_purchase_orders(self, args: dict) -> dict:
        where = []
        if args.get("status"): where.append(f"status='{args['status']}'")
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("requester_id"): where.append(f"requester_id={int(args['requester_id'])}")
        if args.get("start_date"): where.append(f"order_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"order_date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT * FROM purchase_orders{w} ORDER BY order_date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"purchase_orders": df.to_dict(orient="records")}

    async def _handle_purchase_summary(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("start_date"): where.append(f"order_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"order_date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT dept_id, status, COUNT(*) as count, SUM(total_amount) as total_amount FROM purchase_orders{w} GROUP BY dept_id, status ORDER BY dept_id"
        df = pd.read_sql(text(sql), self._engine)
        return {"purchase_summary": df.to_dict(orient="records")}
