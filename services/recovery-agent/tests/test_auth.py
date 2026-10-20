from typing import Annotated

import jwt
import pytest
from fastapi import Depends

from recovery_agent.auth import ROLE_ADMIN, Principal, extract_roles, require_role
from recovery_agent.main import app

from .conftest import make_token


@app.get("/_test/admin-only")
def _admin_only(principal: Annotated[Principal, Depends(require_role(ROLE_ADMIN))]) -> dict[str, str]:
    return {"subject": principal.email}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_liveness_needs_no_token(client):
    assert client.get("/health").json() == {"status": "UP"}


def test_recovery_health_without_token_is_401(client):
    r = client.get("/api/v1/recovery/health")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_recovery_health_with_valid_token_returns_subject_and_roles(client):
    r = client.get("/api/v1/recovery/health", headers=auth(make_token()))
    assert r.status_code == 200
    assert r.json() == {"status": "UP", "subject": "admin@example.test", "roles": ["ROLE_ADMIN"]}


@pytest.mark.parametrize("token", [
    make_token(secret="a-different-secret-that-is-also-32-bytes-long"),
    make_token(exp_offset=-60),
    make_token(sub=None),
    "not-a-jwt",
])
def test_invalid_tokens_are_401(client, token):
    assert client.get("/api/v1/recovery/health", headers=auth(token)).status_code == 401


def test_unsigned_token_is_rejected(client):
    unsigned = jwt.encode({"sub": "admin@example.test", "exp": 9999999999, "role": "ROLE_ADMIN"},
                          key=None, algorithm="none")
    assert client.get("/api/v1/recovery/health", headers=auth(unsigned)).status_code == 401


def test_non_bearer_scheme_is_401(client):
    r = client.get("/api/v1/recovery/health", headers={"Authorization": f"Basic {make_token()}"})
    assert r.status_code == 401


def test_require_role_rejects_customer_with_403(client):
    token = make_token(sub="customer@example.test", role=({"authority": "ROLE_CUSTOMER"},))
    assert client.get("/_test/admin-only", headers=auth(token)).status_code == 403


def test_require_role_accepts_admin(client):
    r = client.get("/_test/admin-only", headers=auth(make_token()))
    assert r.status_code == 200
    assert r.json() == {"subject": "admin@example.test"}


@pytest.mark.parametrize("claim, expected", [
    ([{"authority": "ROLE_ADMIN"}], {"ROLE_ADMIN"}),
    ([{"authority": "ROLE_ADMIN"}, {"authority": "ROLE_CUSTOMER"}], {"ROLE_ADMIN", "ROLE_CUSTOMER"}),
    ("ROLE_CUSTOMER", {"ROLE_CUSTOMER"}),
    (["ROLE_ADMIN"], {"ROLE_ADMIN"}),
    (None, set()),
    ([{"authority": 5}, 7], set()),
    ({"authority": "ROLE_ADMIN"}, set()),
])
def test_extract_roles(claim, expected):
    assert extract_roles(claim) == expected
