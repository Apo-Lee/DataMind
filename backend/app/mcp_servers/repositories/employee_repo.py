# -*- coding: utf-8 -*-
"""员工 Repository"""
from .base import BaseRepository


class EmployeeRepository(BaseRepository):
    """员工表查询封装"""

    def get_by_id(self, eid: int):
        """查单个员工（含部门名）"""
        sql = '''SELECT e.*, d."name" AS dept_name FROM "employees" e
                 LEFT JOIN "departments" d ON e.dept_id = d.id WHERE e."id" = :id'''
        return self._run_dict(sql, {"id": eid})

    def search(self, keyword=None, dept_id=None, position=None, status=None,
               gender=None, education=None, level=None, limit=100):
        """多条件搜索员工"""
        sql = '''SELECT e.*, d."name" AS dept_name FROM "employees" e
                 LEFT JOIN "departments" d ON e.dept_id = d.id'''
        clauses = []
        params = {}
        if dept_id: clauses.append('e."dept_id" = :did'); params["did"] = dept_id
        if position: clauses.append('e."position" = :pos'); params["pos"] = position
        if status: clauses.append('e."status" = :st'); params["st"] = status
        if gender: clauses.append('e."gender" = :gen'); params["gen"] = gender
        if education: clauses.append('e."education" = :edu'); params["edu"] = education
        if level: clauses.append('e."level" = :lv'); params["lv"] = level
        if keyword: clauses.append('e."name" LIKE :kw'); params["kw"] = f"%{keyword}%"
        if clauses: sql += " WHERE " + " AND ".join(clauses)
        return self._run_dict(sql + " LIMIT :lim", {**params, "lim": limit})

    def count_by_dept(self, status=None):
        """按部门统计员工数"""
        where = ' WHERE "status" = :st' if status else ""
        params = {"st": status} if status else {}
        return self._run_dict(f'SELECT "dept_id", COUNT(*) AS cnt FROM "employees"{where} GROUP BY "dept_id" LIMIT 100', params)

    def distribution(self, group_col: str, status=None):
        """按指定列分组统计"""
        where = ' WHERE "status" = :st' if status else ""
        params = {"st": status} if status else {}
        return self._run_dict(f'''SELECT "{group_col}", COUNT(*) AS count FROM "employees"{where} GROUP BY "{group_col}" ORDER BY count DESC''', params)

    def performance_ranking(self, dept_id=None, top_n=20):
        """绩效排名"""
        sql = '''SELECT e."id", e."name", e."dept_id", d."name" AS dept_name,
                 e."position", e."performance_score", e."level"
                 FROM "employees" e LEFT JOIN "departments" d ON e.dept_id = d.id'''
        params = {}
        if dept_id: sql += ' WHERE e."dept_id" = :did'; params["did"] = dept_id
        sql += ' ORDER BY e."performance_score" DESC LIMIT :lim'
        return self._run_dict(sql, {**params, "lim": top_n})

    def attendance_summary(self, employee_id=None, start_date=None, end_date=None, dept_id=None):
        """考勤汇总"""
        clauses = []; params = {}
        if employee_id: clauses.append('a."employee_id" = :eid'); params["eid"] = employee_id
        if start_date: clauses.append('"date" >= :sd'); params["sd"] = start_date
        if end_date: clauses.append('"date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        dept_join = ' AND e."dept_id" = :did' if dept_id else ""
        if dept_id: params["did"] = dept_id
        return self._run_dict(f'''SELECT a."employee_id", e."name" AS employee_name, a."status", COUNT(*) AS days
            FROM "attendance" a LEFT JOIN "employees" e ON a.employee_id = e.id{w} {dept_join}
            GROUP BY a."employee_id", a."status" ORDER BY a."employee_id"''', params)

    def attendance_trend(self, start_date=None, end_date=None):
        """考勤趋势"""
        clauses = []; params = {}
        if start_date: clauses.append('"date" >= :sd'); params["sd"] = start_date
        if end_date: clauses.append('"date" <= :ed'); params["ed"] = end_date
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self._run_dict(f'''SELECT "date", "status", COUNT(*) AS count FROM "attendance"{w} GROUP BY "date", "status" ORDER BY "date"''', params)

    def new_hires(self, start_date=None, end_date=None, dept_id=None, limit=100):
        """新入职员工列表"""
        clauses = []; params = {}
        if start_date: clauses.append('"join_date" >= :sd'); params["sd"] = start_date
        if end_date: clauses.append('"join_date" <= :ed'); params["ed"] = end_date
        if dept_id: clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT "id","name","dept_id","position","level","join_date","education"
            FROM "employees"{w} ORDER BY "join_date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def performance_overview(self, dept_id=None):
        """绩效概况统计"""
        if dept_id:
            stats = self._run_dict(
                '''SELECT COUNT(*) AS total, AVG("performance_score") AS avg_score,
                   MAX("performance_score") AS max_score, MIN("performance_score") AS min_score
                   FROM "employees" WHERE "dept_id" = :did''',
                {"did": int(dept_id)},
            )
            bins = self._run_dict(
                '''SELECT CASE WHEN "performance_score">=90 THEN '优秀'
                    WHEN "performance_score">=80 THEN '良好'
                    WHEN "performance_score">=70 THEN '一般' ELSE '待提升' END AS level,
                    COUNT(*) AS count FROM "employees"
                    WHERE "dept_id" = :did GROUP BY level ORDER BY level''',
                {"did": int(dept_id)},
            )
        else:
            stats = self._run_dict(
                '''SELECT COUNT(*) AS total, AVG("performance_score") AS avg_score,
                   MAX("performance_score") AS max_score, MIN("performance_score") AS min_score
                   FROM "employees"'''
            )
            bins = self._run_dict(
                '''SELECT CASE WHEN "performance_score">=90 THEN '优秀'
                    WHEN "performance_score">=80 THEN '良好'
                    WHEN "performance_score">=70 THEN '一般' ELSE '待提升' END AS level,
                    COUNT(*) AS count FROM "employees" GROUP BY level ORDER BY level'''
            )
        return {"statistics": stats, "distribution": bins}

    def attendance_detail(self, employee_id=None, start_date=None, end_date=None,
                          status=None, limit=100):
        """考勤明细"""
        clauses = []; params = {}
        if employee_id: clauses.append('"employee_id" = :eid'); params["eid"] = int(employee_id)
        if start_date: clauses.append('"date" >= :sd'); params["sd"] = start_date
        if end_date: clauses.append('"date" <= :ed'); params["ed"] = end_date
        if status: clauses.append('"status" = :status'); params["status"] = status
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT * FROM "attendance"{w} ORDER BY "date" DESC LIMIT :limit_val'''
        return self._run_dict(sql, {**params, "limit_val": limit})

    def headcount_trend(self, start_date=None, end_date=None, dept_id=None):
        """月度入职人数趋势"""
        clauses = []; params = {}
        if start_date: clauses.append('"join_date" >= :sd'); params["sd"] = start_date
        if end_date: clauses.append('"join_date" <= :ed'); params["ed"] = end_date
        if dept_id: clauses.append('"dept_id" = :did'); params["did"] = int(dept_id)
        w = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f'''SELECT strftime('%Y-%m', "join_date") AS month,
            COUNT(*) AS hires FROM "employees"{w} GROUP BY month ORDER BY month'''
        return self._run_dict(sql, params)
