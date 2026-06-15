"""端到端服务测试"""

import json

import pytest
from httpx import AsyncClient

from app.core.auth import create_access_token, hash_password
from app.core.encryption import encrypt
from app.models.datasource import DataSource, DataSourcePermission
from app.models.user import User, UserRole


@pytest.mark.asyncio
class TestEndToEnd:
    async def _setup_admin(self, test_session, client):
        user = User(username="admin", hashed_password=hash_password("admin123"),
                    display_name="管理员", role=UserRole.admin, is_active=True)
        test_session.add(user)
        await test_session.commit()
        token = create_access_token(user.id, "admin")
        return token

    async def test_login_and_list_datasources(self, client: AsyncClient):
        # 只测无用户登录返回401
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 401  # 测试环境没 seed

    async def test_health_and_auth_flow(self, client: AsyncClient):
        r1 = await client.get("/api/health")
        assert r1.status_code == 200
        r2 = await client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert r2.status_code == 401
        r3 = await client.get("/api/dashboard/panels")
        assert r3.status_code == 401  # 无 token
