"""行级安全引擎 (V3) — 计算用户的数据可见范围并生成过滤条件

V3 改进：
- 表感知的列注入：只注入目标表实际存在的列
- 统一的 RLS 注入点：不再由 SQLBuilder 内联 RLS
- 支持 dynamic table column checking
"""

import asyncio
import json
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, DataScope
from app.models.datasource import DataSource


class RowLevelSecurityEngine:
    """行级安全引擎：根据用户身份计算数据可见范围"""

    def __init__(self, user: User, datasource: DataSource, db: AsyncSession):
        self.user = user
        self.datasource = datasource
        self.db = db
        self._scope: dict | None = None

    async def compute_data_scope(self) -> dict:
        """计算数据可见范围，返回:
        {
            "mode": "all" | "filtered",
            "allowed_dept_ids": [1, 101, ...],
            "allowed_employee_ids": [1, 2, 3, ...],
            "filter_clauses": {
                "dept_id": "dept_id IN (1, 101, 102)",
                "employee_id": "employee_id IN (1,2,3)",
            }
        }
        """
        if self._scope is not None:
            return self._scope

        if self.user.role == UserRole.admin or self.user.data_scope == DataScope.all:
            self._scope = {"mode": "all"}
            return self._scope

        base_dept_id = self.user.dept_id
        allowed_dept_ids = await asyncio.to_thread(self._compute_allowed_dept_ids, base_dept_id)
        allowed_employee_ids = await self._compute_visible_employees()

        filter_clauses = self._build_filter_clauses(allowed_dept_ids, allowed_employee_ids)

        self._scope = {
            "mode": "filtered",
            "allowed_dept_ids": list(allowed_dept_ids),
            "allowed_employee_ids": list(allowed_employee_ids) if allowed_employee_ids else [],
            "filter_clauses": filter_clauses,
        }
        return self._scope

    def _compute_allowed_dept_ids(self, base_dept_id: int | None) -> set[int]:
        """根据 data_scope 计算允许的部门ID"""
        allowed: set[int] = set()
        scope = self.user.data_scope

        if scope == DataScope.self_only:
            if base_dept_id is not None:
                allowed.add(base_dept_id)
            return allowed

        if scope == DataScope.team:
            if base_dept_id is not None:
                allowed.add(base_dept_id)
            if self.user.employee_id is not None:
                try:
                    from app.agents.factory import agent_factory
                    hr_agent = agent_factory.get_agent_by_tag("hr")
                    if hr_agent is not None:
                        engine = hr_agent.engine
                        with engine.connect() as conn:
                            result = conn.execute(
                                text("SELECT e.dept_id FROM employees e "
                                     "JOIN org_hierarchy o ON e.id = o.descendant_id "
                                     "WHERE o.ancestor_id = :aid AND o.depth = 1"),
                                {"aid": self.user.employee_id}
                            )
                            for row in result:
                                allowed.add(int(row[0]))
                except Exception:
                    pass
            return allowed

        if base_dept_id is not None:
            allowed.add(base_dept_id)

        if scope == DataScope.dept_and_sub:
            if base_dept_id is not None:
                allowed.update(self._get_sub_dept_ids(base_dept_id))
        elif scope == DataScope.cross_dept:
            pass

        if self.user.extra_dept_ids:
            try:
                extra_ids = json.loads(self.user.extra_dept_ids)
                if isinstance(extra_ids, list):
                    allowed.update(int(x) for x in extra_ids)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return allowed

    def _get_sub_dept_ids(self, parent_dept_id: int) -> set[int]:
        """递归获取所有子部门 ID"""
        sub_ids: set[int] = set()
        try:
            from app.agents.factory import agent_factory
            hr_agent = agent_factory.get_agent_by_tag("hr")
            if hr_agent is None:
                return sub_ids
            engine = hr_agent.engine
            visited: set[int] = set()
            queue = [parent_dept_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if current != parent_dept_id:
                    sub_ids.add(current)
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT id FROM departments WHERE parent_dept_id = :pid"),
                        {"pid": current}
                    )
                    for row in result:
                        child_id = int(row[0])
                        if child_id not in visited:
                            queue.append(child_id)
        except Exception:
            pass
        return sub_ids

    async def _compute_visible_employees(self) -> set[int] | None:
        """通过 HR 数据库的 org_hierarchy 物化表计算可见员工"""
        if self.user.employee_id is None:
            return None

        scope = self.user.data_scope

        if scope == DataScope.all:
            return None
        if scope == DataScope.self_only:
            return {self.user.employee_id}
        if scope == DataScope.team:
            max_depth = 1
        elif scope == DataScope.dept:
            return await self._get_employees_by_dept([self.user.dept_id])
        elif scope == DataScope.dept_and_sub:
            dept_ids = await asyncio.to_thread(self._compute_allowed_dept_ids, self.user.dept_id)
            return await self._get_employees_by_dept(list(dept_ids))
        else:
            dept_ids = await asyncio.to_thread(self._compute_allowed_dept_ids, self.user.dept_id)
            return await self._get_employees_by_dept(list(dept_ids))

        try:
            from app.agents.factory import agent_factory
            from app.models.datasource import DataSource as DSModel

            hr_result = await self.db.execute(
                select(DSModel).where(DSModel.business_tag == "hr", DSModel.is_active == True)
            )
            hr_ds = hr_result.scalar_one_or_none()
            if hr_ds is None:
                return None

            hr_agent = agent_factory.get_or_create(hr_ds)
            df = await asyncio.to_thread(
                hr_agent.execute_sql,
                f"SELECT descendant_id FROM org_hierarchy "
                f"WHERE ancestor_id = {self.user.employee_id} AND depth <= {max_depth}"
            )
            if df is not None and not df.empty:
                ids = set(int(x) for x in df["descendant_id"].tolist())
                ids.add(self.user.employee_id)
                return ids
        except Exception:
            pass
        return None

    async def _get_employees_by_dept(self, dept_ids: list[int]) -> set[int] | None:
        """获取指定部门下的所有员工 ID"""
        if not dept_ids:
            return None
        try:
            from app.agents.factory import agent_factory
            from app.models.datasource import DataSource as DSModel

            hr_result = await self.db.execute(
                select(DSModel).where(DSModel.business_tag == "hr", DSModel.is_active == True)
            )
            hr_ds = hr_result.scalar_one_or_none()
            if hr_ds is None:
                return None

            hr_agent = agent_factory.get_or_create(hr_ds)
            dept_id_str = ",".join(str(x) for x in dept_ids)
            df = await asyncio.to_thread(
                hr_agent.execute_sql,
                f"SELECT id FROM employees WHERE dept_id IN ({dept_id_str})"
            )
            if df is not None and not df.empty:
                return set(int(x) for x in df["id"].tolist())
        except Exception:
            pass
        return None

    def _build_filter_clauses(self, dept_ids: set[int], emp_ids: set[int] | None) -> dict[str, str]:
        """生成表级 SQL 过滤子句

        V3: 明确标注每个子句适用于哪些表，供 QueryInterceptor 做列存在性检查。
        """
        clauses = {}

        if dept_ids:
            dept_id_str = ",".join(str(x) for x in dept_ids)
            # dept_id 过滤：适用于 employees, attendance(无此列!), deals, projects 等
            clauses["dept_id"] = f"dept_id IN ({dept_id_str})"

        if emp_ids:
            emp_id_str = ",".join(str(x) for x in emp_ids)
            clauses["employee_id"] = f"employee_id IN ({emp_id_str})"
            # 其他常见外键列，由 QueryInterceptor 按列存在性精确选择
            clauses["id"] = f"id IN ({emp_id_str})"
            clauses["owner_id"] = f"owner_id IN ({emp_id_str})"
            clauses["requester_id"] = f"requester_id IN ({emp_id_str})"
            clauses["approver_id"] = f"approver_id IN ({emp_id_str})"
            clauses["manager_id"] = f"manager_id IN ({emp_id_str})"

        return clauses

    def get_scope_for_agent(self) -> dict | None:
        """返回可注入到 Agent 的权限范围对象"""
        if self._scope is None:
            return None
        return self._scope
