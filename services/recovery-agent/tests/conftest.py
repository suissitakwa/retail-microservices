import time

import jwt
import pytest
from fastapi.testclient import TestClient

from recovery_agent.config import Settings, get_settings
from recovery_agent.main import app

TEST_SECRET = "test-secret-key-that-is-at-least-32-bytes-long"


def make_token(secret: str = TEST_SECRET, *, sub: str | None = "admin@example.test",
               role: object = ({"authority": "ROLE_ADMIN"},), exp_offset: int = 3600, **extra) -> str:
    claims: dict = {"iat": int(time.time()), "exp": int(time.time()) + exp_offset, **extra}
    if sub is not None:
        claims["sub"] = sub
    if role is not None:
        claims["role"] = list(role) if isinstance(role, tuple) else role
    return jwt.encode(claims, secret.encode("utf-8"), algorithm="HS256")


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: Settings(jwt_secret_key=TEST_SECRET)
    yield TestClient(app)
    app.dependency_overrides.clear()
