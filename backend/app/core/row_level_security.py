"""行级安全引擎 (V2) — 计算用户的数据可见范围并生成过滤条件"""
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
                "owner_id": "owner_id IN (1,2,3)",
            }
        }
        """
        if self._scope is not None:
            return self._scope

        # admin 和 data_scope=all → 全量
        if self.user.role == UserRole.admin or self.user.data_scope == DataScope.all:
            self._scope = {"mode": "all"}
            return self._scope

        # 获取用户所在部门
        base_dept_id = self.user.dept_id

        # 计算允许的部门范围
        allowed_dept_ids = await asyncio.to_thread(self._compute_allowed_dept_ids, base_dept_id)

        # 计算允许的员工范围
        allowed_employee_ids = await self._compute_visible_employees()

        # 生成表级过滤子句
        filter_clauses = self._build_filter_clauses(allowed_dept_ids, allowed_employee_ids)

        self._scope = {
            "mode": "filtered",
            "allowed_dept_ids": list(allowed_dept_ids),
            "allowed_employee_ids": list(allowed_employee_ids) if allowed_employee_ids else [],
            "filter_clauses": filter_clauses,
        }
        return self._scope

    def _compute_allowed_dept_ids(self, base_dept_id: int | None) -> set[int]:
        """根据 data_scope 计算允许的部门ID

        self_only:  本部门（个人级表用 employee_id，部门级表用 dept_id）
        team:       本部门 + 直属下级的部门
        dept:       本部门
        dept_and_sub: 本部门 + 递归子部门
        cross_dept: 由 extra_dept_ids 决定
        """
        allowed: set[int] = set()

        scope = self.user.data_scope

        if scope == DataScope.self_only:
            if base_dept_id is not None:
                allowed.add(base_dept_id)
            return allowed

        if scope == DataScope.team:
            # 本部门 + 直属下级的部门
            if base_dept_id is not None:
                allowed.add(base_dept_id)
            if self.user.employee_id is not None:
                try:
                    from app.agents.factory import agent_factory
                    hr_agent = agent_factory.get_agent_by_tag("hr")
                    if hr_agent is not None:
                        engine = hr_agent.engine
                        from sqlalchemy import text
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

        # WHY: dept_and_sub 需要递归获取所有子部门 ID
        if scope == DataScope.dept_and_sub:
            if base_dept_id is not None:
                allowed.update(self._get_sub_dept_ids(base_dept_id))
        elif scope == DataScope.cross_dept:
            # cross_dept 只依赖 extra_dept_ids
            pass

        # 加上额外授权部门
        if self.user.extra_dept_ids:
            try:
                extra_ids = json.loads(self.user.extra_dept_ids)
                if isinstance(extra_ids, list):
                    allowed.update(int(x) for x in extra_ids)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return allowed

    def _get_sub_dept_ids(self, parent_dept_id: int) -> set[int]:
        """递归获取所有子部门 ID（从 HR 数据库的 departments 表）

        使用 BFS 遍历部门树，返回包含所有子孙部门的 ID 集合。
        通过 AgentFactory.get_agent_by_tag 获取 HR 数据源。
        """
        sub_ids: set[int] = set()
        try:
            from app.agents.factory import agent_factory

            hr_agent = agent_factory.get_agent_by_tag("hr")
            if hr_agent is None:
                return sub_ids

            engine = hr_agent.engine  # 同步 SQLAlchemy Engine

            # BFS 遍历子部门
            visited: set[int] = set()
            queue: list[int] = [parent_dept_id]
            with engine.connect() as conn:
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    if current != parent_dept_id:
                        sub_ids.add(current)
                    from sqlalchemy import text
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
        """通过 HR 数据库的 org_hierarchy 物化表计算可见员工

        返回 None 表示不需要员工级过滤（按部门过滤即可）
        返回 set 表示需要按员工过滤
        """
        if self.user.employee_id is None:
            return None

        scope = self.user.data_scope

        if scope == DataScope.all:
            return None  # 全量
        if scope == DataScope.self_only:
            return {self.user.employee_id}
        if scope == DataScope.team:
            # 直属下级 + 自己 (depth <= 1)
            max_depth = 1
        elif scope == DataScope.dept:
            # 本部门 — 按部门过滤 + 员工级过滤
            return await self._get_employees_by_dept([self.user.dept_id])
        elif scope == DataScope.dept_and_sub:
            # 本部门及子部门 — 按部门过滤 + 员工级过滤
            dept_ids = self._compute_allowed_dept_ids(self.user.dept_id)
            return await self._get_employees_by_dept(list(dept_ids))
        else:
            # cross_dept 等 — 按部门过滤 + 员工级过滤
            dept_ids = self._compute_allowed_dept_ids(self.user.dept_id)
            return await self._get_employees_by_dept(list(dept_ids))

        # 查询 HR 数据库的 org_hierarchy 物化表
        try:
            from app.agents.factory import agent_factory
            from app.models.datasource import DataSource as DSModel

            # 找到 HR 数据源
            hr_result = await self.db.execute(
                select(DSModel).where(DSModel.business_tag == "hr", DSModel.is_active == True)
            )
            hr_ds = hr_result.scalar_one_or_none()
            if hr_ds is None:
                return None

            hr_agent = agent_factory.get_or_create(hr_ds)
            # NOTE: employee_id 和 max_depth 均为 int 类型，安全可控
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
        """生成表级 SQL 过滤子句"""
        clauses = {}

        if dept_ids:
            dept_id_str = ",".join(str(x) for x in dept_ids)
            clauses["dept_id"] = f"dept_id IN ({dept_id_str})"
            clauses["owner_dept_id"] = f"owner_dept_id IN ({dept_id_str})"

        if emp_ids:
            emp_id_str = ",".join(str(x) for x in emp_ids)
            emp_clause = f"id IN ({emp_id_str})"
            # employees 表的主键是 id，不是 employee_id
            # 但其他表用 employee_id/owner_id/requester_id 等
            clauses["id"] = emp_clause
            clauses["employee_id"] = f"employee_id IN ({emp_id_str})"
            for col in ["owner_id", "requester_id", "approver_id", "manager_id"]:
                clauses[col] = f"{col} IN ({emp_id_str})"

        return clauses

    def get_scope_for_agent(self) -> dict | None:
        """返回可注入到 Agent 的权限范围对象（同步接口，需先 await compute_data_scope）"""
        if self._scope is None:
            return None
        return self._scope
