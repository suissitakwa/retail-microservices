import os
import time
import uuid

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import AsyncConnectionPool

from recovery_agent.config import Settings, get_settings
from recovery_agent.db import apply_schema
from recovery_agent.main import app

TEST_SECRET = "test-secret-key-that-is-at-least-32-bytes-long"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://recovery_user:recovery_password@localhost:5439/recovery_db")


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


def _db_available() -> bool:
    try:
        psycopg.connect(TEST_DATABASE_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="recovery-db not reachable on TEST_DATABASE_URL")


@pytest.fixture
async def db_pool():
    """A pool bound to a fresh, throwaway schema so tests never see each other's rows."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f"CREATE SCHEMA {schema}")
    pool = AsyncConnectionPool(TEST_DATABASE_URL, min_size=1, max_size=3, open=False,
                               kwargs={"autocommit": True, "options": f"-c search_path={schema}"})
    await pool.open()
    async with pool.connection() as conn:
        await apply_schema(conn)
    try:
        yield pool
    finally:
        await pool.close()
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(f"DROP SCHEMA {schema} CASCADE")
