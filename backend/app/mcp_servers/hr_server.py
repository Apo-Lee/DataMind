"""
HR MCP Server — 完整业务工具覆盖
人力资源: 组织架构、员工、考勤、绩效、薪酬（权限内）
"""
import logging, pandas as pd
from sqlalchemy import text
from .base_sql import SQLMCPServer, MCPTool

logger = logging.getLogger(__name__)
DB_URL = "sqlite:///../demo_data/hr_demo.sqlite"

class HRMCPServer(SQLMCPServer):
    def __init__(self):
        super().__init__("HR系统", "hr", DB_URL)

    def _foreign_keys(self) -> dict:
        return {("employees","departments"):("dept_id","id"),("attendance","employees"):("employee_id","id")}

    def _register_business_tools(self):
        # ─── 组织架构 ───
        self.register_tool(MCPTool(
            name="get_org_structure",
            description="获取完整组织架构树（部门层级关系、各部门负责人、人数）",
            parameters={},
        ), self._handle_org_structure)

        self.register_tool(MCPTool(
            name="get_department_detail",
            description="获取单个部门详细信息（含成员列表、预算、负责人）",
            parameters={"dept_id": {"type": "integer", "description": "部门ID"}},
            required=["dept_id"],
        ), self._handle_dept_detail)

        self.register_tool(MCPTool(
            name="get_department_budget",
            description="查看各部门预算情况",
            parameters={},
        ), self._handle_dept_budget)

        # ─── 员工信息 ───
        self.register_tool(MCPTool(
            name="get_employee_detail",
            description="获取员工详细信息（基本信息、部门、绩效、联系方式）",
            parameters={"employee_id": {"type": "integer", "description": "员工ID"}},
            required=["employee_id"],
        ), self._handle_employee_detail)

        self.register_tool(MCPTool(
            name="search_employees",
            description="按条件搜索员工（支持按部门/岗位/职级/状态/性别/学历筛选）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID"},
                "position": {"type": "string", "description": "岗位名称"},
                "status": {"type": "string", "description": "状态（在职/离职）"},
                "gender": {"type": "string", "description": "性别（M/F）"},
                "education": {"type": "string", "description": "学历"},
                "level": {"type": "string", "description": "职级"},
                "keyword": {"type": "string", "description": "姓名关键词"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_search_employees)

        self.register_tool(MCPTool(
            name="get_employee_distribution",
            description="获取员工分布统计（支持按部门/岗位/职级/性别/学历分组）",
            parameters={
                "group_by": {
                    "type": "string",
                    "enum": ["dept_id", "position", "level", "gender", "education", "status", "position_category"],
                    "description": "分组字段",
                }
            },
            required=["group_by"],
        ), self._handle_employee_distribution)

        self.register_tool(MCPTool(
            name="get_new_hires",
            description="获取新员工列表（按入职日期范围筛选）",
            parameters={
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "limit": {"type": "integer", "default": 50},
            },
        ), self._handle_new_hires)

        # ─── 绩效管理 ───
        self.register_tool(MCPTool(
            name="get_performance_overview",
            description="获取绩效概览（平均分/最高/最低/分布，可按部门筛选）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
            },
        ), self._handle_performance_overview)

        self.register_tool(MCPTool(
            name="get_performance_ranking",
            description="获取员工绩效排名（支持按部门/岗位筛选，可分页）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "top_n": {"type": "integer", "default": 20, "description": "返回前N名"},
            },
        ), self._handle_performance_ranking)

        # ─── 考勤管理 ───
        self.register_tool(MCPTool(
            name="get_attendance_summary",
            description="获取考勤汇总（按员工统计出勤/请假/缺勤/迟到天数，支持时间范围）",
            parameters={
                "employee_id": {"type": "integer", "description": "员工ID（可选，不传则全公司）"},
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
            },
        ), self._handle_attendance_summary)

        self.register_tool(MCPTool(
            name="get_attendance_detail",
            description="获取考勤明细记录（按员工/日期范围查看打卡记录）",
            parameters={
                "employee_id": {"type": "integer", "description": "员工ID"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "status": {"type": "string", "description": "考勤状态（出勤/请假/缺勤/迟到）"},
                "limit": {"type": "integer", "default": 100},
            },
        ), self._handle_attendance_detail)

        self.register_tool(MCPTool(
            name="get_attendance_trend",
            description="获取考勤趋势（按日/周/月统计出勤率变化）",
            parameters={
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
            },
        ), self._handle_attendance_trend)

        # ─── 人员变动 ───
        self.register_tool(MCPTool(
            name="get_headcount_trend",
            description="获取人员变动趋势（按月统计入职/离职人数）",
            parameters={
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "dept_id": {"type": "integer", "description": "部门ID（可选）"},
            },
        ), self._handle_headcount_trend)

    # ═══════════════════════════════════════
    # 实现处理器
    # ═══════════════════════════════════════

    async def _handle_org_structure(self, args: dict) -> dict:
        depts = pd.read_sql(text("SELECT * FROM departments"), self._engine)
        hierarchy = pd.read_sql(text("SELECT * FROM org_hierarchy"), self._engine)
        emp_count = pd.read_sql(text("SELECT dept_id, COUNT(*) as cnt FROM employees WHERE status='在职' GROUP BY dept_id"), self._engine)
        return {"departments": depts.to_dict(orient="records"), "hierarchy": hierarchy.to_dict(orient="records"), "employee_counts": emp_count.to_dict(orient="records")}

    async def _handle_dept_detail(self, args: dict) -> dict:
        did = int(args["dept_id"])
        dept = pd.read_sql(text(f"SELECT * FROM departments WHERE id={did}"), self._engine)
        members = pd.read_sql(text(f"SELECT id,name,position,level,status,join_date,performance_score,manager_id FROM employees WHERE dept_id={did}"), self._engine)
        subs = pd.read_sql(text(f"SELECT * FROM departments WHERE parent_dept_id={did}"), self._engine)
        return {"department": dept.to_dict(orient="records"), "members": members.to_dict(orient="records"), "sub_departments": subs.to_dict(orient="records")}

    async def _handle_dept_budget(self, args: dict) -> dict:
        df = pd.read_sql(text("SELECT d.id,d.name,d.budget,d.manager_name,d.location FROM departments d ORDER BY d.budget DESC"), self._engine)
        return {"departments": df.to_dict(orient="records")}

    async def _handle_employee_detail(self, args: dict) -> dict:
        eid = int(args["employee_id"])
        df = pd.read_sql(text(f"SELECT e.*, d.name as dept_name FROM employees e LEFT JOIN departments d ON e.dept_id=d.id WHERE e.id={eid}"), self._engine)
        att = pd.read_sql(text(f"SELECT status,COUNT(*) as cnt FROM attendance WHERE employee_id={eid} GROUP BY status"), self._engine) if not df.empty else pd.DataFrame()
        return {"employee": df.to_dict(orient="records"), "attendance_summary": att.to_dict(orient="records")}

    async def _handle_search_employees(self, args: dict) -> dict:
        where = []
        if args.get("dept_id"): where.append(f"e.dept_id={int(args['dept_id'])}")
        if args.get("position"): where.append(f"e.position='{args['position']}'")
        if args.get("status"): where.append(f"e.status='{args['status']}'")
        if args.get("gender"): where.append(f"e.gender='{args['gender']}'")
        if args.get("education"): where.append(f"e.education='{args['education']}'")
        if args.get("level"): where.append(f"e.level='{args['level']}'")
        if args.get("keyword"): where.append(f"e.name LIKE '%{args['keyword']}%'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT e.*, d.name as dept_name FROM employees e LEFT JOIN departments d ON e.dept_id=d.id{w} LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"employees": df.to_dict(orient="records"), "total": len(df)}

    async def _handle_employee_distribution(self, args: dict) -> dict:
        gb = args["group_by"]
        sql = f"SELECT {gb}, COUNT(*) as count FROM employees WHERE status='在职' GROUP BY {gb} ORDER BY count DESC"
        df = pd.read_sql(text(sql), self._engine)
        return {"distribution": df.to_dict(orient="records"), "group_by": gb}

    async def _handle_new_hires(self, args: dict) -> dict:
        where = []
        if args.get("start_date"): where.append(f"join_date >= '{args['start_date']}'")
        if args.get("end_date"): where.append(f"join_date <= '{args['end_date']}'")
        if args.get("dept_id"): where.append(f"dept_id = {int(args['dept_id'])}")
        w = " WHERE " + " AND ".join(where) if where else " WHERE 1=1"
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT id,name,dept_id,position,level,join_date,education FROM employees{w} ORDER BY join_date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"new_hires": df.to_dict(orient="records")}

    async def _handle_performance_overview(self, args: dict) -> dict:
        where = f" WHERE dept_id={int(args['dept_id'])}" if args.get("dept_id") else ""
        sql = f"SELECT COUNT(*) as total, AVG(performance_score) as avg_score, MAX(performance_score) as max_score, MIN(performance_score) as min_score FROM employees{where}"
        stats = pd.read_sql(text(sql), self._engine)
        bins = pd.read_sql(text(f"SELECT CASE WHEN performance_score>=90 THEN '优秀' WHEN performance_score>=80 THEN '良好' WHEN performance_score>=70 THEN '一般' ELSE '待提升' END as level, COUNT(*) as count FROM employees{where} GROUP BY level ORDER BY level"), self._engine)
        return {"statistics": stats.to_dict(orient="records"), "distribution": bins.to_dict(orient="records")}

    async def _handle_performance_ranking(self, args: dict) -> dict:
        where = f" WHERE e.dept_id={int(args['dept_id'])}" if args.get("dept_id") else ""
        top_arg = args.get("top_n", 20)
        if top_arg is None: top_arg = 20
        top = min(int(top_arg), 200)
        if top <= 0: top = 20
        sql = f"SELECT e.id,e.name,e.dept_id,d.name as dept_name,e.position,e.performance_score,e.level FROM employees e LEFT JOIN departments d ON e.dept_id=d.id{where} ORDER BY e.performance_score DESC LIMIT {top}"
        df = pd.read_sql(text(sql), self._engine)
        return {"ranking": df.to_dict(orient="records")}

    async def _handle_attendance_summary(self, args: dict) -> dict:
        where = []
        if args.get("employee_id"): where.append(f"a.employee_id={int(args['employee_id'])}")
        if args.get("start_date"): where.append(f"a.date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"a.date<='{args['end_date']}'")
        dept_filter = f" WHERE e.dept_id={int(args['dept_id'])}" if args.get("dept_id") else ""
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT a.employee_id, e.name as employee_name, a.status, COUNT(*) as days FROM attendance a LEFT JOIN employees e ON a.employee_id=e.id{w} GROUP BY a.employee_id, a.status ORDER BY a.employee_id"
        df = pd.read_sql(text(sql), self._engine)
        return {"summary": df.to_dict(orient="records")}

    async def _handle_attendance_detail(self, args: dict) -> dict:
        where = []
        if args.get("employee_id"): where.append(f"employee_id={int(args['employee_id'])}")
        if args.get("start_date"): where.append(f"date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"date<='{args['end_date']}'")
        if args.get("status"): where.append(f"status='{args['status']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        limit_arg = args.get("limit", 100)
        if limit_arg is None: limit_arg = 100
        limit = min(int(limit_arg), 5000)
        if limit <= 0: limit = 100
        sql = f"SELECT * FROM attendance{w} ORDER BY date DESC LIMIT {limit}"
        df = pd.read_sql(text(sql), self._engine)
        return {"records": df.to_dict(orient="records")}

    async def _handle_attendance_trend(self, args: dict) -> dict:
        where = []
        if args.get("start_date"): where.append(f"date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"date<='{args['end_date']}'")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT date, status, COUNT(*) as count FROM attendance{w} GROUP BY date, status ORDER BY date"
        df = pd.read_sql(text(sql), self._engine)
        return {"trend": df.to_dict(orient="records")}

    async def _handle_headcount_trend(self, args: dict) -> dict:
        where = []
        if args.get("start_date"): where.append(f"join_date>='{args['start_date']}'")
        if args.get("end_date"): where.append(f"join_date<='{args['end_date']}'")
        if args.get("dept_id"): where.append(f"dept_id={int(args['dept_id'])}")
        w = " WHERE " + " AND ".join(where) if where else ""
        sql = f"SELECT strftime('%Y-%m', join_date) as month, COUNT(*) as hires FROM employees{w} GROUP BY month ORDER BY month"
        df = pd.read_sql(text(sql), self._engine)
        return {"monthly_hires": df.to_dict(orient="records")}
