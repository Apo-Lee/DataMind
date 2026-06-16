import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
import sys; sys.path.insert(0, ".")
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.user import User

async def get_users():
    engine = create_async_engine(settings.database_url)
    session = async_sessionmaker(engine, class_=AsyncSession)()
    result = await session.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()
    
    # Find key test users
    test_users = {}
    for u in users:
        if u.username in ["emp1", "emp2", "emp17", "admin"]:
            test_users[u.username] = {
                "id": u.id,
                "display_name": u.display_name,
                "role": u.role.value if hasattr(u.role, 'value') else u.role,
                "data_scope": u.data_scope.value if hasattr(u.data_scope, 'value') else u.data_scope,
                "dept_id": u.dept_id,
                "employee_id": u.employee_id,
            }
    await session.close()
    await engine.dispose()
    return test_users

users = asyncio.run(get_users())
for name, info in users.items():
    print(f"{name}: {info}")
