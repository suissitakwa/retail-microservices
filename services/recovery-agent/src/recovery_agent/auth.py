"""Stateless validation of tokens issued by customer-service (the only JWT issuer)."""

from dataclasses import dataclass, field
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from recovery_agent.config import Settings, get_settings

ROLE_ADMIN = "ROLE_ADMIN"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    email: str
    roles: frozenset[str]
    # Raw token, forwarded to downstream services so reads run with the caller's own rights
    token: str = field(default="", repr=False, compare=False)

    def has_role(self, role: str) -> bool:
        return role in self.roles


def extract_roles(claim: Any) -> frozenset[str]:
    """customer-service serialises Spring authorities: [{"authority": "ROLE_ADMIN"}].
    A plain string or list of strings is accepted too."""
    if claim is None:
        return frozenset()
    if isinstance(claim, str):
        return frozenset({claim})
    if isinstance(claim, list):
        roles = set()
        for item in claim:
            if isinstance(item, dict) and isinstance(item.get("authority"), str):
                roles.add(item["authority"])
            elif isinstance(item, str):
                roles.add(item)
        return frozenset(roles)
    return frozenset()


def decode_token(token: str, settings: Settings) -> Principal:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.encode("utf-8"),
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token",
                            headers={"WWW-Authenticate": "Bearer"}) from e
    return Principal(email=claims["sub"], roles=extract_roles(claims.get("role")), token=token)


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    return decode_token(credentials.credentials, settings)


def require_role(role: str):
    def dependency(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if not principal.has_role(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"{role} required")
        return principal

    return dependency
