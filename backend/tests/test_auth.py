"""认证模块测试"""

import pytest
from httpx import AsyncClient

from app.core.auth import hash_password, verify_password, create_access_token, decode_token


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "mypassword123"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False


class TestJWT:
    def test_create_and_decode_access_token(self):
        token = create_access_token("user-123", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_decode_invalid_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_token("not.a.valid.token")
        assert exc.value.status_code == 401


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
