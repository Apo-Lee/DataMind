# -*- coding: utf-8 -*-
"""费控/财务 Repository — Finance 数据访问层

封装 budgets / expenses / travel_expenses / cost_centers 四张表的查询。
"""
from .base import BaseRepository


class FinanceRepository(BaseRepository):
    """费控数据查询"""

    # ——— 预算 ———

    def budget_overview(self, dept_id=None, year=None, quarter=None):
        """预算总览（按部门/年度/季度汇总）"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if year:
            clauses.append('"year" = :year'); params["year"] = int(year)
        if quarter:
            clauses.append('"quarter" = :quarter'); params["quarter"] = int(quarter)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        tail = "" if clauses else " LIMIT :limit_val"
        sql = f'''SELECT "dept_id", "year", "quarter",
            SUM("amount") AS total_budget, SUM("used") AS total_used,
            SUM("remaining_adj") AS total_remaining
            FROM "budgets"{w} GROUP BY "dept_id", "year", "quarter"
            ORDER BY "year", "quarter"{tail}'''
        final_params = {**params, "limit_val": 5000} if not clauses else params
        return self._run_dict(sql, final_params)

    def budget_detail(self, dept_id=None, year=None, quarter=None, category=None):
        """预算明细"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if year:
            clauses.append('"year" = :year'); params["year"] = int(year)
        if quarter:
            clauses.append('"quarter" = :quarter'); params["quarter"] = int(quarter)
        if category:
            clauses.append('"category" = :cat'); params["cat"] = category
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        tail = "" if clauses else " LIMIT :limit_val"
        sql = f'''SELECT * FROM "budgets"{w}
            ORDER BY "year", "quarter", "dept_id", "category"{tail}'''
        final_params = {**params, "limit_val": 5000} if not clauses else params
        return self._run_dict(sql, final_params)

    def budget_execution_rate(self, year=None, quarter=None):
        """预算执行率排名"""
        clauses = []
        params = {}
        if year:
            clauses.append('"year" = :year'); params["year"] = int(year)
        if quarter:
            clauses.append('"quarter" = :quarter'); params["quarter"] = int(quarter)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT "dept_id", "category", "amount" AS budget, "used",
            ROUND("used" * 100.0 / "amount", 1) AS execution_rate,
            "remaining_adj" AS remaining
            FROM "budgets"{w} ORDER BY execution_rate DESC'''
        return self._run_dict(sql, params)

    # ——— 费用 ———

    def expense_summary(self, start_date=None, end_date=None, dept_id=None, group_by="category"):
        """费用汇总（按指定维度分组 + 总计）"""
        clauses = []
        params = {}
        if start_date:
            clauses.append('"date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"date" <= :ed'); params["ed"] = end_date
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""

        gb_col = f'"{group_by}"' if group_by in {"category", "dept_id", "status", "expense_type"} else '"category"'
        summary = self._run_dict(
            f'''SELECT {gb_col}, COUNT(*) AS count, SUM("amount") AS total_amount,
                AVG("amount") AS avg_amount
                FROM "expenses"{w} GROUP BY {gb_col} ORDER BY total_amount DESC''',
            params,
        )
        total = self._run_dict(
            f'''SELECT COUNT(*) AS total_count, SUM("amount") AS grand_total
                FROM "expenses"{w}''',
            params,
        )
        return {"expense_summary": summary, "total": total}

    def search_expenses(self, category=None, status=None, dept_id=None,
                        employee_id=None, min_amount=None, max_amount=None,
                        start_date=None, end_date=None, limit=100):
        """搜索费用记录"""
        clauses = []
        params = {}
        if category:
            clauses.append('"category" = :cat'); params["cat"] = category
        if status:
            clauses.append('"status" = :status'); params["status"] = status
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if employee_id:
            clauses.append('"employee_id" = :eid'); params["eid"] = int(employee_id)
        if min_amount is not None:
            clauses.append('"amount" >= :min_amt'); params["min_amt"] = float(min_amount)
        if max_amount is not None:
            clauses.append('"amount" <= :max_amt'); params["max_amt"] = float(max_amount)
        if start_date:
            clauses.append('"date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT * FROM "expenses"{w} ORDER BY "date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def expense_trend(self, start_date=None, end_date=None, dept_id=None, category=None):
        """费用月度趋势"""
        clauses = []
        params = {}
        if start_date:
            clauses.append('"date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"date" <= :ed'); params["ed"] = end_date
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if category:
            clauses.append('"category" = :cat'); params["cat"] = category
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT strftime('%Y-%m', "date") AS month,
            COUNT(*) AS count, SUM("amount") AS total
            FROM "expenses"{w} GROUP BY month ORDER BY month'''
        return self._run_dict(sql, params)

    # ——— 差旅 ———

    def travel_expenses(self, employee_id=None, destination=None,
                        start_date=None, end_date=None, limit=100):
        """差旅费用明细"""
        clauses = []
        params = {}
        if employee_id:
            clauses.append('t."employee_id" = :eid'); params["eid"] = int(employee_id)
        if destination:
            clauses.append('t."destination" = :dest'); params["dest"] = destination
        if start_date:
            clauses.append('t."departure_date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('t."return_date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT t.*, e."amount" AS total_expense_amount, e."category", e."description"
            FROM "travel_expenses" t LEFT JOIN "expenses" e ON t.expense_id = e.id{w}
            ORDER BY t."departure_date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def travel_summary(self, group_by="destination", start_date=None, end_date=None):
        """差旅费用汇总"""
        clauses = []
        params = {}
        if start_date:
            clauses.append('"departure_date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"return_date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""

        gb_col = {'destination': '"destination"', 'employee_id': '"employee_id"'}.get(group_by, '"destination"')
        sql = f'''SELECT {gb_col}, COUNT(*) AS trip_count,
            SUM("transport_fee" + "hotel_fee" + "meal_fee" + "other_fee") AS total_cost
            FROM "travel_expenses"{w} GROUP BY {gb_col} ORDER BY total_cost DESC'''
        return self._run_dict(sql, params)

    # ——— 成本中心 ———

    def cost_centers(self, dept_id=None, fiscal_year=None):
        """成本中心信息（含剩余比率）"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if fiscal_year:
            clauses.append('"fiscal_year" = :fy'); params["fy"] = int(fiscal_year)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        tail = "" if clauses else " LIMIT :limit_val"
        sql = f'''SELECT *, ROUND("budget_remaining" * 100.0 / "budget_total", 1) AS remaining_rate
            FROM "cost_centers"{w} ORDER BY "fiscal_year" DESC, "dept_id"{tail}'''
        final_params = {**params, "limit_val": 5000} if not clauses else params
        return self._run_dict(sql, final_params)
