"""种子脚本 V2 — 预定义系统数据源 + 从 HR 系统同步初始用户和权限

外部数据库映射 (V2):
- hr_demo.sqlite    → HR 系统 (数据锚点, 含组织架构)
- crm_demo.sqlite   → CRM 系统
- finance_demo.sqlite → 费控系统
- erp_demo.sqlite   → ERP 系统

系统用户:
- admin: 管理员 (手动创建，不参与 HR 同步)
- 其他用户: 通过 HR 同步自动创建
"""

import asyncio
import logging
import os

from sqlalchemy import select
from app.database import async_session, init_db
from app.models.user import User, UserRole, DataScope
from app.models.datasource import DataSource, DataSourcePermission
from app.core.auth import hash_password
from app.core.encryption import encrypt
from app.config import settings

logger = logging.getLogger(__name__)


async def seed():
    await init_db()
    async with async_session() as db:
        # ========== 1. 创建 admin 账户 ==========
        admin_result = await db.execute(select(User).where(User.username == "admin"))
        admin = admin_result.scalar_one_or_none()
        if admin is None:
            admin = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                display_name="系统管理员",
                role=UserRole.admin,
                is_active=True,
                source="manual",
                data_scope=DataScope.all,
            )
            db.add(admin)
            await db.flush()
            print("[SEED] Admin 用户已创建: admin / admin123")

        # ========== 2. 确保 V2 demo 数据库存在 ==========
        demo_dir = settings.demo_data_dir or "./demo_data"
        try:
            import importlib.util
            v2_path = os.path.join(demo_dir, "seed_unified_v2.py")
            if os.path.exists(v2_path):
                spec = importlib.util.spec_from_file_location("seed_unified_v2", v2_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.create_hr_database()
                mod.create_crm_database()
                mod.create_finance_database()
                mod.create_erp_database()
                print("[SEED] V2 统一 demo 数据库已生成")
            else:
                print("[SEED] 警告: seed_unified_v2.py 未找到，请先运行生成脚本")
        except Exception as e:
            print(f"[SEED] V2 demo 数据库生成警告: {e}")

        # ========== 3. 预定义 4 个系统数据源 ==========
        ds_configs = [
            ("HR 系统",   "sqlite", f"{demo_dir}/hr_demo.sqlite",      0, "hr_demo",      "hr"),
            ("CRM 系统",  "sqlite", f"{demo_dir}/crm_demo.sqlite",     0, "crm_demo",     "crm"),
            ("费控系统",  "sqlite", f"{demo_dir}/finance_demo.sqlite", 0, "finance_demo", "finance"),
            ("ERP 系统",  "sqlite", f"{demo_dir}/erp_demo.sqlite",     0, "erp_demo",     "erp"),
        ]
        created_ds = {}
        for name, db_type, host, port, db_name, tag in ds_configs:
            r = await db.execute(select(DataSource).where(DataSource.name == name))
            ds = r.scalar_one_or_none()
            if ds is None:
                ds = DataSource(
                    name=name, db_type=db_type, host=host, port=port, db_name=db_name,
                    username="", password_encrypted=encrypt(""), business_tag=tag,
                    is_system=True,
                )
                db.add(ds)
                await db.flush()
                print(f"[SEED] 系统数据源已创建: {name} ({tag})")
            created_ds[tag] = ds

        # ========== 4. 设置数据源权限 (角色级) ==========
        # 清除旧角色权限
        old_perms = (await db.execute(
            select(DataSourcePermission).where(DataSourcePermission.grant_type == "role")
        )).scalars().all()
        for p in old_perms:
            await db.delete(p)

        # 权限矩阵 V2
        perm_matrix = {
            "hr":      [("role", "admin"), ("role", "hr_director"), ("role", "dept_ceo"),
                        ("role", "dept_manager"), ("role", "employee"), ("role", "viewer"),
                        ("role", "sales_manager")],  # 销售经理需要看下属考勤/绩效
            "crm":     [("role", "admin"), ("role", "dept_ceo"), ("role", "sales_manager"),
                        ("role", "dept_manager"), ("role", "employee")],
            "finance": [("role", "admin"), ("role", "finance_director"), ("role", "finance_bp"),
                        ("role", "dept_ceo"), ("role", "dept_manager"), ("role", "employee"),
                        ("role", "hr_director")],
            "erp":     [("role", "admin"), ("role", "dept_ceo"), ("role", "dept_manager"),
                        ("role", "employee"), ("role", "sales_manager")],
        }

        for tag, grants in perm_matrix.items():
            ds = created_ds.get(tag)
            if not ds:
                continue
            for grant_type, grant_target in grants:
                db.add(DataSourcePermission(
                    datasource_id=ds.id,
                    grant_type=grant_type,
                    grant_target=grant_target,
                    can_query=True,
                    row_filter_scope="default",  # 使用用户默认 data_scope
                ))
            logger.info(f"[SEED] {tag} 权限已设置: {len(grants)} 个角色授权")

        # ========== 5. HR 同步 → 创建系统用户 ==========
        try:
            from app.agents.factory import agent_factory
            from app.core.hr_sync import sync_hr_to_users

            hr_ds = created_ds.get("hr")
            if hr_ds:
                agent = agent_factory.get_or_create(hr_ds)
                sync_log = await sync_hr_to_users(db, agent)
                print(f"[SEED] HR 同步完成: 创建 {sync_log.created_users} 用户, "
                      f"更新 {sync_log.updated_users}, 停用 {sync_log.deactivated_users}")
        except Exception as e:
            print(f"[SEED] HR 同步警告 (首次启动填0正常): {e}")

        await db.commit()

        logger.info("=" * 50)
        logger.info("  DataMind V2 系统初始化完成")
        logger.info("=" * 50)

        # 验证
        user_count = (await db.execute(select(User).where(User.is_active == True))).scalars().all()
        ds_count = (await db.execute(select(DataSource).where(DataSource.is_active == True))).scalars().all()
        logger.info(f"  系统用户: {len(user_count)} 人 (含 {sum(1 for u in user_count if u.source == 'hr_sync')} 个HR同步用户)")
        logger.info(f"  系统数据源: {len(ds_count)} 个")
        logger.info(f"  管理员: admin / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
