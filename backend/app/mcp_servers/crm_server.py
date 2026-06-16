"""
CRM MCP Server — 完整业务工具覆盖
客户关系管理: 客户、商机、跟进、销售目标、业绩
"""
import logging, pandas as pd
from sqlalchemy import text
from .base_sql import SQLMCPServer, MCPTool

logger = logging.getLogger(__name__)
DB_URL = "sqlite:///../demo_data/crm_demo.sqlite"

class CRMMCPServer(SQLMCPServer):
    def __init__(self):
        super().__init__("CRM系统", "crm", DB_URL)

    def _foreign_keys(self) -> dict:
        return {("deals","customers"):("customer_id","id"),("follow_ups","customers"):("customer_id","id")}

    def _register_business_tools(self):
        # ─── 客户管理 ───
        self.register_tool(MCPTool(
            name="search_customers",
            description="搜索客户（按行业/等级/负责人/关键词筛选，支持分页）",
            parameters={
                "keyword": {"type": "string", "description": "客户名称关键词"},
                "industry": {"type": "string", "description": "行业"},
                "level": {"type": "string", "description": "客户等级（A/B/C）"},
                "owner_id": {"type": "integer", "description": "负责人ID"},
                "dept_id": {"type": "integer", "description": "归属部门ID"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_search_customers)

        self.register_tool(MCPTool(
            name="get_customer_detail",
            description="获取客户详细信息（基本信息、关联商机、跟进记录）",
            parameters={"customer_id": {"type": "integer", "description": "客户ID"}},
            required=["customer_id"],
        ), self._handle_customer_detail)

        self.register_tool(MCPTool(
            name="get_customer_distribution",
            description="获取客户分布统计（按行业/等级/来源等维度）",
            parameters={
                "group_by": {"type": "string", "enum": ["industry","level"], "description": "分组字段"},
            },
            required=["group_by"],
        ), self._handle_customer_distribution)

        # ─── 商机管理 ───
        self.register_tool(MCPTool(
            name="get_sales_pipeline",
            description="获取销售管道概览（按阶段汇总商机数量/金额）",
            parameters={},
        ), self._handle_sales_pipeline)

        self.register_tool(MCPTool(
            name="search_deals",
            description="搜索商机（按状态/阶段/金额/负责人/时间范围筛选）",
            parameters={
                "status": {"type": "string", "description": "状态（赢单/输单/进行中）"},
                "stage": {"type": "string", "description": "销售阶段"},
                "owner_id": {"type": "integer", "description": "负责人ID"},
                "dept_id": {"type": "integer", "description": "部门ID"},
                "customer_id": {"type": "integer", "description": "客户ID"},
                "min_amount": {"type": "number", "description": "最小金额"},
                "max_amount": {"type": "number", "description": "最大金额"},
                "start_date": {"type": "string", "description": "创建日期开始 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "创建日期结束 YYYY-MM-DD"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_search_deals)

        self.register_tool(MCPTool(
            name="get_deal_summary",
            description="获取商机汇总统计（赢单率/总金额/平均金额，可按部门/负责人筛选）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "owner_id": {"type": "integer", "description": "负责人ID（可选）"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
            },
        ), self._handle_deal_summary)

        # ─── 跟进记录 ───
        self.register_tool(MCPTool(
            name="get_follow_ups",
            description="获取跟进记录（按客户/负责人/类型筛选）",
            parameters={
                "customer_id": {"type": "integer", "description": "客户ID"},
                "employee_id": {"type": "integer", "description": "跟进人ID"},
                "type": {"type": "string", "description": "跟进类型（上门拜访/电话/邮件）"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_follow_ups)

        # ─── 销售目标与业绩 ───
        self.register_tool(MCPTool(
            name="get_sales_targets",
            description="获取销售目标（按部门/负责人/年度/季度查询目标与完成情况）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID"},
                "employee_id": {"type": "integer", "description": "负责人ID"},
                "year": {"type": "integer", "description": "年份"},
                "quarter": {"type": "integer", "description": "季度"},
            },
        ), self._handle_sales_targets)

        self.register_tool(MCPTool(
            name="get_team_performance",
            description="获取团队销售业绩排名（按负责人汇总目标完成率）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "year": {"type": "integer", "description": "年份"},
                "quarter": {"type": "integer", "description": "季度"},
            },
        ), self._handle_team_performance)

        self.register_tool(MCPTool(
            name="get_deal_performance_ranking",
            description="获取商机业绩排行（按负责人汇总赢单金额排名）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "limit": {"type": "integer", "default": 20},
            },
        ), self._handle_deal_performance_ranking)

    # ═══════════════════════════════════════
    # 实现处理器
    # ═══════════════════════════════════════

    async def _handle_search_customers(self, args: dict) -> dict:
        where = []
        if args.get("keyword"): where.append(f"c.name LIKE '%{args['keyword']}%'")
        if args.get("industry"): where.append(f"c.industry='{args['industry']}'")
        if args.get("level"): where.append(f"c.level='{args['level']}'")
        if args.get("owner_id"): where.append(f"c.owner_id={int(args['owner_id'])}")
        if args.get("dept_id"): where.append(f"c.owner_dept_id={int(args['dept_id'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT c.*, (SELECT COUNT(*) FROM deals WHERE customer_id=c.id) as deal_count FROM customers c{w} ORDER BY c.created_date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"customers": df.to_dict(orient="records")}

    async def _handle_customer_detail(self, args: dict) -> dict:
        cid = int(args["customer_id"])
        customer = pd.read_sql(text(f"SELECT * FROM customers WHERE id={cid}"), self._engine)
        deals = pd.read_sql(text(f"SELECT * FROM deals WHERE customer_id={cid} ORDER BY created_date DESC"), self._engine)
        follow_ups = pd.read_sql(text(f"SELECT * FROM follow_ups WHERE customer_id={cid} ORDER BY date DESC"), self._engine)
        return {"customer": customer.to_dict(orient="records"), "deals": deals.to_dict(orient="records"), "follow_ups": follow_ups.to_dict(orient="records")}

    async def _handle_customer_distribution(self, args: dict) -> dict:
        gb = args["group_by"]
        df = pd.read_sql(text(f"SELECT {gb}, COUNT(*) as count FROM customers GROUP BY {gb} ORDER BY count DESC"), self._engine)
        return {"distribution": df.to_dict(orient="records")}

    async def _handle_sales_pipeline(self, args: dict) -> dict:
        df = pd.read_sql(text("SELECT stage, COUNT(*) as deal_count, SUM(amount) as total_amount FROM deals WHERE status!='输单' GROUP BY stage ORDER BY total_amount DESC"), self._engine)
        return {"pipeline": df.to_dict(orient="records")}

    async def _handle_search_deals(self, args: dict) -> dict:
        where = []
        if args.get("status"): where.append(f"d.status='{args['status']}'")
        if args.get("stage"): where.append(f"d.stage='{args['stage']}'")
        if args.get("owner_id"): where.append(f"d.owner_id={int(args['owner_id'])}")
        if args.get("dept_id"): where.append(f"d.dept_id={int(args['dept_id'])}")
        if args.get("customer_id"): where.append(f"d.customer_id={int(args['customer_id'])}")
        if args.get("min_amount"): where.append(f"d.amount>={args['min_amount']}")
        if args.get("max_amount"): where.append(f"d.amount<={args['max_amount']}")
        if args.get("start_date"): where.append(f"d.created_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"d.created_date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT d.*, c.name as customer_name FROM deals d LEFT JOIN customers c ON d.customer_id=c.id{w} ORDER BY d.created_date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"deals": df.to_dict(orient="records")}

    async def _handle_deal_summary(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("owner_id"): where.append(f"owner_id={int(args['owner_id'])}")
        if args.get("start_date"): where.append(f"created_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"created_date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        total = pd.read_sql(text(f"SELECT COUNT(*) as total, SUM(amount) as total_amount, AVG(amount) as avg_amount FROM deals{w}"), self._engine)
        won = pd.read_sql(text(f"SELECT COUNT(*) as won_count, SUM(amount) as won_amount FROM deals{w} AND status='赢单'" if w else "SELECT COUNT(*) as won_count, SUM(amount) as won_amount FROM deals WHERE status='赢单'"), self._engine)
        by_status = pd.read_sql(text(f"SELECT status, COUNT(*) as count, SUM(amount) as total FROM deals{w} GROUP BY status"), self._engine)
        return {"overview": total.to_dict(orient="records"), "won": won.to_dict(orient="records"), "by_status": by_status.to_dict(orient="records")}

    async def _handle_follow_ups(self, args: dict) -> dict:
        where = []
        if args.get("customer_id"): where.append(f"f.customer_id={int(args['customer_id'])}")
        if args.get("employee_id"): where.append(f"f.employee_id={int(args['employee_id'])}")
        if args.get("type"): where.append(f"f.type='{args['type']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT f.*, c.name as customer_name FROM follow_ups f LEFT JOIN customers c ON f.customer_id=c.id{w} ORDER BY f.date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"follow_ups": df.to_dict(orient="records")}

    async def _handle_sales_targets(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("employee_id"): where.append(f"employee_id={int(args['employee_id'])}")
        if args.get("year"): where.append(f"year={int(args['year'])}")
        if args.get("quarter"): where.append(f"quarter={int(args['quarter'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        df = pd.read_sql(text(f"SELECT *, ROUND(achieved_amount*100.0/target_amount,1) as achievement_rate FROM sales_targets{w} ORDER BY year, quarter, employee_id"), self._engine)
        return {"targets": df.to_dict(orient="records")}

    async def _handle_team_performance(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        if args.get("year"): where.append(f"year={int(args['year'])}")
        if args.get("quarter"): where.append(f"quarter={int(args['quarter'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT employee_id, SUM(target_amount) as total_target, SUM(achieved_amount) as total_achieved, ROUND(SUM(achieved_amount)*100.0/SUM(target_amount),1) as achievement_rate FROM sales_targets{w} GROUP BY employee_id ORDER BY achievement_rate DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"performance": df.to_dict(orient="records")}

    async def _handle_deal_performance_ranking(self, args: dict) -> dict:
        where = f" WHERE d.dept_id={int(args['dept_id'])}" if args.get("dept_id") else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT d.owner_id, e.name as owner_name, COUNT(*) as deal_count, SUM(d.amount) as total_amount FROM deals d LEFT JOIN employees e ON d.owner_id=e.id{where} GROUP BY d.owner_id ORDER BY total_amount DESC LIMIT {limit}"
        # employees only exists in HR db, so use owner_id instead
        sql = f"SELECT d.owner_id, COUNT(*) as deal_count, SUM(d.amount) as total_amount FROM deals d{where} GROUP BY d.owner_id ORDER BY total_amount DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"ranking": df.to_dict(orient="records")}
