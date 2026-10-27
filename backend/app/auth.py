"""Role-Based Access Control (RBAC) and API Key / Bearer authentication middleware.

Enables enterprise multi-tenant access control while supporting seamless local development.
"""

from enum import Enum
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.config import Settings


class Role(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    AUDITOR = "auditor"
    ANONYMOUS = "anonymous"


ROLE_HIERARCHY = {
    Role.ADMIN: 4,
    Role.ENGINEER: 3,
    Role.AUDITOR: 2,
    Role.ANONYMOUS: 1,
}


class AuthUser(BaseModel):
    user_id: str
    tenant_id: str
    role: Role


def get_current_user(
    x_api_key: Annotated[Optional[str], Header()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
    settings: Settings = Depends(Settings),
) -> AuthUser:
    """Authenticates inbound requests via API Key or Bearer Token.

    When AUTH_ENABLED is False, defaults to an Admin user for seamless local development.
    """
    auth_enabled = getattr(settings, "auth_enabled", False)
    if not auth_enabled:
        return AuthUser(user_id="dev-user", tenant_id="default-tenant", role=Role.ADMIN)

    # 1. Check API Key
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key or Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Pre-configured keys for enterprise tiers
    admin_key = getattr(settings, "admin_api_key", "trace-admin-secret-key")
    engineer_key = getattr(settings, "engineer_api_key", "trace-engineer-key")
    auditor_key = getattr(settings, "auditor_api_key", "trace-auditor-key")

    if token == admin_key:
        return AuthUser(user_id="admin-1", tenant_id="enterprise", role=Role.ADMIN)
    if token == engineer_key:
        return AuthUser(user_id="eng-1", tenant_id="enterprise", role=Role.ENGINEER)
    if token == auditor_key:
        return AuthUser(user_id="auditor-1", tenant_id="compliance", role=Role.AUDITOR)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid credentials or insufficient permissions",
    )


def require_role(min_role: Role):
    """Dependency factory ensuring user holds at least the specified privilege tier."""
    def role_checker(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        user_rank = ROLE_HIERARCHY.get(user.role, 0)
        required_rank = ROLE_HIERARCHY.get(min_role, 0)
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires minimum role of '{min_role.value}', current role is '{user.role.value}'",
            )
        return user
    return role_checker
