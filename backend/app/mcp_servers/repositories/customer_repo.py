# -*- coding: utf-8 -*-
"""客户/商机 Repository — CRM 数据访问层

封装 customers / deals / follow_ups / sales_targets 四张表的查询，
替代各 handler 中直接写 pd.read_sql 的旧模式。
"""
from .base import BaseRepository


class CustomerRepository(BaseRepository):
    """CRM 客户关系数据查询"""

    # ——— 客户 ———

    def search_customers(self, keyword=None, industry=None, level=None,
                         owner_id=None, dept_id=None, limit=100):
        """多条件搜索客户（含各客户的商机数）"""
        clauses = []
        params = {}
        if keyword:
            clauses.append('c."name" LIKE :kw'); params["kw"] = f"%{keyword}%"
        if industry:
            clauses.append('c."industry" = :industry'); params["industry"] = industry
        if level:
            clauses.append('c."level" = :level'); params["level"] = level
        if owner_id:
            clauses.append('c."owner_id" = :oid'); params["oid"] = int(owner_id)
        if dept_id:
            clauses.append('c."owner_dept_id" = :did'); params["did"] = int(dept_id)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT c.*, (SELECT COUNT(*) FROM "deals" WHERE "customer_id" = c.id) AS deal_count
            FROM "customers" c{w} ORDER BY c."created_date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def get_by_id(self, cid: int):
        """查单个客户（基本信息）"""
        return self._run_dict(
            'SELECT * FROM "customers" WHERE "id" = :id', {"id": cid}
        )

    def deals_by_customer(self, cid: int):
        """某客户的全部商机"""
        return self._run_dict(
            '''SELECT * FROM "deals" WHERE "customer_id" = :cid ORDER BY "created_date"''',
            {"cid": cid},
        )

    def follow_ups_by_customer(self, cid: int):
        """某客户的全部跟进记录"""
        return self._run_dict(
            '''SELECT * FROM "follow_ups" WHERE "customer_id" = :cid ORDER BY "date"''',
            {"cid": cid},
        )

    def distribution(self, group_col: str):
        """按指定列（industry/level 等）分组统计客户"""
        # group_col 仅允许来自工具 enum（industry/level），不做任意拼接暴露
        assert group_col in {"industry", "level"}, f"非法分组列: {group_col}"
        return self._run_dict(
            f'''SELECT "{group_col}", COUNT(*) AS count FROM "customers"
                GROUP BY "{group_col}" ORDER BY count DESC'''
        )

    # ——— 商机 ———

    def sales_pipeline(self):
        """销售管道：按阶段汇总商机数量/金额（排除输单）"""
        return self._run_dict(
            '''SELECT "stage", COUNT(*) AS deal_count, SUM("amount") AS total_amount
               FROM "deals" WHERE "status" != :excluded
               GROUP BY "stage" ORDER BY total_amount DESC''',
            {"excluded": "输单"},
        )

    def search_deals(self, status=None, stage=None, owner_id=None, dept_id=None,
                     customer_id=None, min_amount=None, max_amount=None,
                     start_date=None, end_date=None, limit=100):
        """多条件搜索商机（含客户名）"""
        clauses = []
        params = {}
        if status:
            clauses.append('d."status" = :status'); params["status"] = status
        if stage:
            clauses.append('d."stage" = :stage'); params["stage"] = stage
        if owner_id:
            clauses.append('d."owner_id" = :oid'); params["oid"] = int(owner_id)
        if dept_id:
            clauses.append('d."dept_id" = :did'); params["did"] = int(dept_id)
        if customer_id:
            clauses.append('d."customer_id" = :cid'); params["cid"] = int(customer_id)
        if min_amount is not None:
            clauses.append('d."amount" >= :min_amt'); params["min_amt"] = float(min_amount)
        if max_amount is not None:
            clauses.append('d."amount" <= :max_amt'); params["max_amt"] = float(max_amount)
        if start_date:
            clauses.append('d."created_date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('d."created_date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT d.*, c."name" AS customer_name FROM "deals" d
            LEFT JOIN "customers" c ON d.customer_id = c.id{w}
            ORDER BY d."created_date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def deal_summary(self, dept_id=None, owner_id=None, start_date=None, end_date=None):
        """商机汇总（总数/总金额/均额 + 赢单 + 按状态分组）"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if owner_id:
            clauses.append('"owner_id" = :oid'); params["oid"] = int(owner_id)
        if start_date:
            clauses.append('"created_date" >= :sd'); params["sd"] = start_date
        if end_date:
            clauses.append('"created_date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""

        overview = self._run_dict(
            f'''SELECT COUNT(*) AS total, SUM("amount") AS total_amount,
                AVG("amount") AS avg_amount FROM "deals"{w}''',
            params,
        )
        won_where = (w + ' AND "status" = :won') if clauses else ' WHERE "status" = :won'
        won = self._run_dict(
            f'''SELECT COUNT(*) AS won_count, SUM("amount") AS won_amount
                FROM "deals"{won_where}''',
            {**params, "won": "赢单"},
        )
        by_status = self._run_dict(
            f'''SELECT "status", COUNT(*) AS count, SUM("amount") AS total
                FROM "deals"{w} GROUP BY "status"''',
            params,
        )
        return {"overview": overview, "won": won, "by_status": by_status}

    def deal_performance_ranking(self, dept_id=None, limit=100):
        """商机业绩排行（按负责人汇总赢单金额）"""
        where = ' WHERE d."dept_id" = :did' if dept_id else ""
        params = {"did": int(dept_id)} if dept_id else {}
        sql = f'''SELECT d."owner_id", COUNT(*) AS deal_count, SUM(d."amount") AS total_amount
            FROM "deals" d{where}
            GROUP BY d."owner_id" ORDER BY total_amount DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    # ——— 跟进 ———

    def search_follow_ups(self, customer_id=None, employee_id=None, type=None, limit=100):
        """搜索跟进记录（含客户名）"""
        clauses = []
        params = {}
        if customer_id:
            clauses.append('f."customer_id" = :cid'); params["cid"] = int(customer_id)
        if employee_id:
            clauses.append('f."employee_id" = :eid'); params["eid"] = int(employee_id)
        if type:
            clauses.append('f."type" = :type'); params["type"] = type
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT f.*, c."name" AS customer_name FROM "follow_ups" f
            LEFT JOIN "customers" c ON f.customer_id = c.id{w}
            ORDER BY f."date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    # ——— 销售目标与业绩 ———

    def sales_targets(self, dept_id=None, employee_id=None, year=None, quarter=None):
        """销售目标（含达成率）"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if employee_id:
            clauses.append('"employee_id" = :eid'); params["eid"] = int(employee_id)
        if year:
            clauses.append('"year" = :year'); params["year"] = int(year)
        if quarter:
            clauses.append('"quarter" = :quarter'); params["quarter"] = int(quarter)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        # 无筛选时加 LIMIT 防止全表返回
        tail = "" if clauses else " LIMIT :limit_val"
        sql = f'''SELECT *, ROUND("achieved_amount" * 100.0 / "target_amount", 1) AS achievement_rate
            FROM "sales_targets"{w} ORDER BY "year", "quarter", "employee_id"{tail}'''
        final_params = {**params, "limit_val": 5000} if not clauses else params
        return self._run_dict(sql, final_params)

    def team_performance(self, dept_id=None, year=None, quarter=None):
        """团队业绩排名（按负责人汇总达成率）"""
        clauses = []
        params = {}
        if dept_id:
            clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        if year:
            clauses.append('"year" = :year'); params["year"] = int(year)
        if quarter:
            clauses.append('"quarter" = :quarter'); params["quarter"] = int(quarter)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT "employee_id", SUM("target_amount") AS total_target,
            SUM("achieved_amount") AS total_achieved,
            ROUND(SUM("achieved_amount") * 100.0 / SUM("target_amount"), 1) AS achievement_rate
            FROM "sales_targets"{w} GROUP BY "employee_id" ORDER BY achievement_rate DESC'''
        return self._run_dict(sql, params)
