# -*- coding: utf-8 -*-
"""企业资源 Repository — ERP 数据访问层

封装 projects / project_dept / resources / inventory / purchase_orders 五张表的查询。
"""
from .base import BaseRepository


class ErpRepository(BaseRepository):
    """ERP 数据查询"""

    # ——— 项目 ———

    def project_overview(self):
        """项目总览：按状态+优先级汇总 + 总计"""
        by_status = self._run_dict(
            '''SELECT "status", COUNT(*) AS count, SUM("budget") AS total_budget,
               SUM("actual_cost") AS total_cost
               FROM "projects" GROUP BY "status"'''
        )
        by_priority = self._run_dict(
            '''SELECT "priority", COUNT(*) AS count
               FROM "projects" GROUP BY "priority" ORDER BY "priority"'''
        )
        total = self._run_dict(
            '''SELECT COUNT(*) AS total, SUM("budget") AS total_budget,
               SUM("actual_cost") AS total_cost FROM "projects"'''
        )
        return {"by_status": by_status, "by_priority": by_priority, "total": total}

    def search_projects(self, status=None, priority=None, dept_id=None,
                        manager_id=None, keyword=None, limit=100):
        """搜索项目"""
        clauses = []
        params = {}
        if status:
            clauses.append('"status" = :status'); params["status"] = status
        if priority:
            clauses.append('"priority" = :prio'); params["prio"] = priority
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if manager_id:
            clauses.append('"manager_id" = :mid'); params["mid"] = int(manager_id)
        if keyword:
            clauses.append('"name" LIKE :kw'); params["kw"] = f"%{keyword}%"
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT * FROM "projects"{w} ORDER BY "start_date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def get_project_by_id(self, pid: int):
        """查单个项目"""
        return self._run_dict(
            'SELECT * FROM "projects" WHERE "id" = :id', {"id": pid}
        )

    def project_depts(self, pid: int):
        """项目参与的部门"""
        return self._run_dict(
            '''SELECT * FROM "project_dept" WHERE "project_id" = :pid''', {"pid": pid}
        )

    def project_resources(self, pid: int):
        """项目的资源分配"""
        return self._run_dict(
            '''SELECT * FROM "resources" WHERE "project_id" = :pid''', {"pid": pid}
        )

    def project_budget_analysis(self, dept_id=None):
        """项目预算 vs 实际成本"""
        if dept_id:
            return self._run_dict(
                '''SELECT "id", "name", "project_code", "status", "budget", "actual_cost",
                    ROUND("actual_cost" * 100.0 / "budget", 1) AS cost_rate,
                    ("budget" - "actual_cost") AS remaining
                    FROM "projects" WHERE "dept_id" = :did ORDER BY cost_rate DESC''',
                {"did": int(dept_id)},
            )
        return self._run_dict(
            '''SELECT "id", "name", "project_code", "status", "budget", "actual_cost",
                ROUND("actual_cost" * 100.0 / "budget", 1) AS cost_rate,
                ("budget" - "actual_cost") AS remaining
                FROM "projects" ORDER BY cost_rate DESC'''
        )

    def project_timeline(self, status=None, limit=100):
        """项目时间线"""
        if status:
            return self._run_dict(
                '''SELECT "id", "name", "project_code", "status", "start_date",
                    "end_date", "priority" FROM "projects"
                    WHERE "status" = :status ORDER BY "start_date" LIMIT :limit_val''',
                {"status": status, "limit_val": limit},
            )
        return self._run_dict(
            '''SELECT "id", "name", "project_code", "status", "start_date",
                "end_date", "priority" FROM "projects"
                ORDER BY "start_date" LIMIT :limit_val''',
            {"limit_val": limit},
        )

    # ——— 资源 ———

    def resource_allocation(self, project_id=None, employee_id=None):
        """资源分配（含项目名/状态）"""
        clauses = []
        params = {}
        if project_id:
            clauses.append('r."project_id" = :pid'); params["pid"] = int(project_id)
        if employee_id:
            clauses.append('r."employee_id" = :eid'); params["eid"] = int(employee_id)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        tail = "" if clauses else " LIMIT :limit_val"
        sql = f'''SELECT r.*, p."name" AS project_name, p."status" AS project_status
            FROM "resources" r LEFT JOIN "projects" p ON r.project_id = p.id{w}
            ORDER BY r."project_id", r."role"{tail}'''
        final_params = {**params, "limit_val": 5000} if not clauses else params
        return self._run_dict(sql, final_params)

    def resource_cost_analysis(self, project_id=None):
        """资源成本分析"""
        if project_id:
            return self._run_dict(
                '''SELECT "project_id", "role", COUNT(*) AS headcount,
                    SUM("daily_cost") AS total_daily_cost
                    FROM "resources" WHERE "project_id" = :pid
                    GROUP BY "project_id", "role" ORDER BY "project_id", total_daily_cost DESC''',
                {"pid": int(project_id)},
            )
        return self._run_dict(
            '''SELECT "project_id", "role", COUNT(*) AS headcount,
                SUM("daily_cost") AS total_daily_cost
                FROM "resources" GROUP BY "project_id", "role"
                ORDER BY "project_id", total_daily_cost DESC'''
        )

    # ——— 库存 ———

    def inventory_status(self, warehouse=None, category=None, keyword=None,
                         low_stock_only=False, limit=100):
        """库存状态（含 computed stock_status）"""
        clauses = []
        params = {}
        if warehouse:
            clauses.append('"warehouse" = :wh'); params["wh"] = warehouse
        if category:
            clauses.append('"category" = :cat'); params["cat"] = category
        if keyword:
            clauses.append('"name" LIKE :kw'); params["kw"] = f"%{keyword}%"
        if low_stock_only:
            clauses.append('"quantity" <= "min_stock"')
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT *, ("quantity" * "unit_price") AS total_value,
            ("quantity" - "min_stock") AS stock_above_min,
            CASE WHEN "quantity" <= "min_stock" THEN '预警'
                 WHEN "quantity" <= "max_stock" * 0.3 THEN '偏低' ELSE '正常' END AS stock_status
            FROM "inventory"{w} ORDER BY stock_status, "category", "name" LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def inventory_summary(self, group_by="warehouse"):
        """库存汇总（按仓库/类别）"""
        gb_col = group_by if group_by in {"warehouse", "category"} else "warehouse"
        return self._run_dict(
            f'''SELECT "{gb_col}", COUNT(*) AS item_count, SUM("quantity") AS total_quantity,
                SUM("quantity" * "unit_price") AS total_value,
                SUM(CASE WHEN "quantity" <= "min_stock" THEN 1 ELSE 0 END) AS low_stock_count
                FROM "inventory" GROUP BY "{gb_col}"'''
        )

    def low_stock_alerts(self, dept_id=None):
        """低库存预警列表"""
        if dept_id:
            rows = self._run_dict(
                '''SELECT *, ("quantity" * "unit_price") AS total_value,
                    ("min_stock" - "quantity") AS shortage
                    FROM "inventory"
                    WHERE "dept_id" = :did AND "quantity" <= "min_stock"
                    ORDER BY shortage DESC''',
                {"did": int(dept_id)},
            )
        else:
            rows = self._run_dict(
                '''SELECT *, ("quantity" * "unit_price") AS total_value,
                    ("min_stock" - "quantity") AS shortage
                    FROM "inventory" WHERE "quantity" <= "min_stock"
                    ORDER BY shortage DESC'''
            )
        return {"alerts": rows, "total_alerts": len(rows)}

    # ——— 采购 ———

    def search_purchase_orders(self, status=None, dept_id=None, requester_id=None,
                               start_date=None, end_date=None, limit=100):
        """搜索采购单"""
        clauses = []
        params = {}
        if status:
            clauses.append('"status" = :status'); params["status"] = status
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if requester_id:
            clauses.append('"requester_id" = :rid'); params["rid"] = int(requester_id)
        if start_date:
            clauses.append('"order_date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"order_date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT * FROM "purchase_orders"{w} ORDER BY "order_date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def purchase_summary(self, dept_id=None, start_date=None, end_date=None):
        """采购汇总（按部门/状态分组）"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if start_date:
            clauses.append('"order_date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"order_date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        tail = "" if clauses else " LIMIT :limit_val"
        sql = f'''SELECT "dept_id", "status", COUNT(*) AS count, SUM("total_amount") AS total_amount
            FROM "purchase_orders"{w} GROUP BY "dept_id", "status" ORDER BY "dept_id"{tail}'''
        final_params = {**params, "limit_val": 5000} if not clauses else params
        return self._run_dict(sql, final_params)
