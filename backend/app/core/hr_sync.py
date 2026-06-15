"""HR 同步引擎 (V2) — 从 HR 数据库同步员工到系统用户表"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.user import User, UserRole, DataScope
from app.models.datasource import DataSource, DataSourcePermission
from app.models.audit_log import HrSyncLog


# 职位到角色的映射规则
def determine_role(position: str, position_category: str, dept_id: int) -> UserRole:
    """根据职位和部门推断系统角色"""
    pos_lower = position.lower()
    cat_lower = (position_category or "").lower()

    # 财务人员（按 category 优先）
    if cat_lower == "财务" or "财务" in position:
        if "总监" in position:
            return UserRole.finance_director
        return UserRole.finance_bp

    # HR 人员（按 category 优先）
    if cat_lower == "hr" or "人力" in pos_lower or "HR" in position:
        if "总监" in position:
            return UserRole.hr_director
        return UserRole.viewer  # HR 普通人员默认只读

    # 销售人员（按 category 优先）
    if cat_lower == "销售" or "销售" in pos_lower:
        if "总监" in position:
            return UserRole.dept_ceo
        if "经理" in position and ("区域" in position or "大区" in position):
            return UserRole.sales_manager
        return UserRole.employee

    # 部门负责人/总监（按 category 判断部门归属）
    if "总监" in position:
        if dept_id == 3:
            return UserRole.hr_director
        if dept_id == 4:
            return UserRole.finance_director
        return UserRole.dept_ceo

    # 子部门经理（按 category 判断部门归属）
    if "经理" in position or "主管" in position:
        if cat_lower == "hr":
            return UserRole.viewer
        if cat_lower == "财务":
            return UserRole.finance_bp
        if "区域" in position or "大区" in position:
            return UserRole.sales_manager
        return UserRole.dept_manager

    # 普通员工（按 category 判断）
    if cat_lower == "hr":
        return UserRole.viewer
    if cat_lower == "财务":
        return UserRole.finance_bp
    return UserRole.employee


# 角色到数据源标签的映射
ROLE_DATASOURCE_MAP = {
    UserRole.admin:             ["hr", "crm", "finance", "erp"],
    UserRole.hr_director:       ["hr", "finance"],  # HR总监需要看下属报销数据
    UserRole.finance_director:  ["finance", "hr"],  # 财务总监按设计仅看财务+HR，跨系统权限由管理员单独授予
    UserRole.finance_bp:        ["finance"],
    UserRole.dept_ceo:          ["hr", "crm", "finance", "erp"],
    UserRole.dept_manager:      ["hr", "crm", "finance", "erp"],
    UserRole.sales_manager:     ["crm", "erp", "hr"],  # 销售经理需要看下属考勤/绩效
    UserRole.employee:          ["hr", "crm", "finance", "erp"],
    UserRole.viewer:            ["hr"],  # 修复: viewer 可以看到 HR 数据（只读范围）
}

# 角色到默认 data_scope 的映射
ROLE_SCOPE_MAP = {
    UserRole.admin:             DataScope.all,
    UserRole.hr_director:       DataScope.dept_and_sub,
    UserRole.finance_director:  DataScope.all,
    UserRole.finance_bp:        DataScope.dept,
    UserRole.dept_ceo:          DataScope.team,
    UserRole.dept_manager:      DataScope.team,
    UserRole.sales_manager:     DataScope.team,
    UserRole.employee:          DataScope.self_only,
    UserRole.viewer:            DataScope.dept,
}


def generate_username(name: str, employee_id: int) -> str:
    """生成系统用户名

    WHY: 中文名无法可靠转换为拼音首字母，统一使用 emp+工号 确保唯一可预测
    """
    return f"emp{employee_id}"


async def sync_hr_to_users(db: AsyncSession, hr_agent) -> HrSyncLog:
    """从 HR 数据库同步员工到系统用户表

    逻辑:
    1. 读取 HR 所有在职/试用期员工
    2. 按 position + position_category 映射角色
    3. 创建新用户或更新已有用户 (按 employee_id 匹配)
    4. 标记已离职/不在HR系统的用户为 is_active=False
    5. 授予默认数据源权限
    """
    import logging
    log = logging.getLogger(__name__)

    sync_log = HrSyncLog(started_at=datetime.now(timezone.utc), status="running")
    db.add(sync_log)
    await db.flush()

    errors = []
    created = 0
    updated = 0
    deactivated = 0

    def _safe_int(val):
        """安全转换为 int，处理 pandas NaN"""
        if val is None:
            return None
        try:
            import numpy as np
            if isinstance(val, (float, np.floating)) and np.isnan(val):
                return None
        except ImportError:
            pass
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    try:
        # 1. 读取 HR 数据库的员工数据
        hr_employees_df = await asyncio.to_thread(
            hr_agent.execute_sql,
            "SELECT id, name, dept_id, manager_id, position, position_category, "
            "status, phone, email FROM employees WHERE status IN ('在职', '试用期')"
        )
        hr_employee_map = {}
        for _, row in hr_employees_df.iterrows():
            emp_id = _safe_int(row["id"])
            if emp_id is None:
                continue
            hr_employee_map[emp_id] = row
        sync_log.total_hr_employees = len(hr_employee_map)

        # 2. 获取现有系统用户
        existing_result = await db.execute(
            select(User).where(User.employee_id.isnot(None))
        )
        existing_users = {u.employee_id: u for u in existing_result.scalars().all()}

        # 3. 处理每个 HR 员工
        for emp_id, emp_row in hr_employee_map.items():
            try:
                emp_id_int = emp_id
                role = determine_role(
                    emp_row.get("position", ""),
                    emp_row.get("position_category", ""),
                    _safe_int(emp_row.get("dept_id")) or 0,
                )
                data_scope = ROLE_SCOPE_MAP.get(role, DataScope.team)

                if emp_id_int in existing_users:
                    # 更新已有用户
                    user = existing_users[emp_id_int]
                    user.display_name = emp_row["name"]
                    user.role = role
                    user.dept_id = _safe_int(emp_row.get("dept_id"))
                    user.manager_id = _safe_int(emp_row.get("manager_id"))
                    user.data_scope = data_scope
                    user.hr_synced_at = datetime.now(timezone.utc)
                    user.is_active = True
                    user.source = "hr_sync"
                    updated += 1
                else:
                    # 创建新用户
                    username = generate_username(emp_row["name"], emp_id_int)
                    existing_name = await db.execute(
                        select(User).where(User.username == username)
                    )
                    if existing_name.scalar_one_or_none():
                        username = f"{username}_{emp_id_int}"

                    user = User(
                        username=username,
                        hashed_password=hash_password(f"emp{emp_id_int}@{str(emp_row.get('phone', '0000'))[-4:]}"),
                        display_name=emp_row["name"],
                        role=role,
                        is_active=True,
                        employee_id=emp_id_int,
                        dept_id=_safe_int(emp_row.get("dept_id")),
                        manager_id=_safe_int(emp_row.get("manager_id")),
                        data_scope=data_scope,
                        hr_synced_at=datetime.now(timezone.utc),
                        source="hr_sync",
                    )
                    db.add(user)
                    await db.flush()
                    created += 1
                    existing_users[emp_id_int] = user

            except Exception as e:
                errors.append(f"员工 {emp_id}: {str(e)}")

        # 4. 停用不在 HR 系统中的用户
        for emp_id, user in existing_users.items():
            if emp_id not in hr_employee_map:
                if user.is_active:
                    user.is_active = False
                    user.hr_synced_at = datetime.now(timezone.utc)
                    deactivated += 1

        # 5. 授予数据源权限 (V2.1: 为每个用户独立按角色授予)
        await _grant_default_permissions(db, existing_users)

        # 6. 更新同步日志
        sync_log.status = "success" if not errors else "partial_success"
        sync_log.created_users = created
        sync_log.updated_users = updated
        sync_log.deactivated_users = deactivated
        if errors:
            sync_log.errors = {"details": errors[:20]}
        sync_log.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        sync_log.status = "failed"
        sync_log.errors = {"error": str(e)}
        sync_log.completed_at = datetime.now(timezone.utc)
        log.exception(f"HR 同步失败: {e}")

    await db.commit()
    return sync_log


async def _grant_default_permissions(db: AsyncSession, users_map: dict):
    """为用户授予默认数据源权限（根据各自角色）

    策略：先清理所有用户级权限，再按当前角色重新授予。
    避免角色降级后旧权限残留导致权限漂移。
    """
    # 获取所有激活的数据源
    ds_result = await db.execute(
        select(DataSource).where(DataSource.is_active == True)
    )
    datasources = ds_result.scalars().all()
    ds_tag_map = {ds.business_tag: ds for ds in datasources}

    for emp_id, user in users_map.items():
        # 1. 清理旧用户级权限（避免角色降级后权限残留）
        old_perms = (await db.execute(
            select(DataSourcePermission).where(
                DataSourcePermission.grant_type == "user",
                DataSourcePermission.grant_target == user.id,
            )
        )).scalars().all()
        for p in old_perms:
            await db.delete(p)

        # 2. 按当前角色授予新权限
        allowed_tags = ROLE_DATASOURCE_MAP.get(user.role, [])
        for tag in allowed_tags:
            ds = ds_tag_map.get(tag)
            if ds is None:
                continue
            db.add(DataSourcePermission(
                datasource_id=ds.id,
                grant_type="user",
                grant_target=user.id,
                can_query=True,
            ))
