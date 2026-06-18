# -*- coding: utf-8 -*-
"""部门/组织架构 Repository — HR 数据访问层

封装 departments / org_hierarchy 两张表的查询。
"""
from .base import BaseRepository


class DepartmentRepository(BaseRepository):
    """部门与组织架构数据查询"""

    def org_structure(self):
        """完整组织架构树（部门列表 + 层级关系 + 各部门在职人数）"""
        depts = self._run_dict('SELECT * FROM "departments"')
        hierarchy = self._run_dict('SELECT * FROM "org_hierarchy"')
        emp_counts = self._run_dict(
            '''SELECT "dept_id", COUNT(*) AS cnt FROM "employees"
               WHERE "status" = :s GROUP BY "dept_id"''',
            {"s": "在职"},
        )
        return {"departments": depts, "hierarchy": hierarchy, "employee_counts": emp_counts}

    def get_by_id(self, did: int):
        """查单个部门"""
        return self._run_dict(
            'SELECT * FROM "departments" WHERE "id" = :id', {"id": did}
        )

    def members(self, did: int, cols=None):
        """某部门的成员列表（有限列）"""
        select = ", ".join(f'"{c}"' for c in cols) if cols else "*"
        return self._run_dict(
            f'''SELECT {select} FROM "employees" WHERE "dept_id" = :did''',
            {"did": did},
        )

    def sub_departments(self, parent_did: int):
        """子部门列表"""
        return self._run_dict(
            '''SELECT * FROM "departments" WHERE "parent_dept_id" = :pid''',
            {"pid": parent_did},
        )

    def budget_list(self):
        """按预算排序的部门列表（供预算工具用）"""
        return self._run_dict(
            '''SELECT "id", "name", "budget", "manager_name", "location"
               FROM "departments" ORDER BY "budget" DESC'''
        )
