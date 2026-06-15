"""数据库连接 & API 路由集成测试"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAPIHealth:
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    async def test_auth_login_without_users(self, client: AsyncClient):
        """未创建用户时登录应返回 401"""
        resp = await client.post("/api/auth/login", json={
            "username": "nobody", "password": "wrong",
        })
        assert resp.status_code == 401

    async def test_protected_route_without_token(self, client: AsyncClient):
        resp = await client.get("/api/users")
        assert resp.status_code == 401
