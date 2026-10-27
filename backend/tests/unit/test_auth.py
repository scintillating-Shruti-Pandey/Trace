"""Unit tests for enterprise RBAC and API authentication middleware."""

import pytest
from fastapi import HTTPException

from app.auth import AuthUser, Role, get_current_user, require_role
from app.config import Settings


def test_auth_disabled_returns_admin_by_default():
    settings = Settings()
    user = get_current_user(settings=settings)
    assert user.role == Role.ADMIN
    assert user.tenant_id == "default-tenant"


def test_auth_enabled_missing_credentials_raises_401():
    settings = Settings()
    settings.auth_enabled = True
    with pytest.raises(HTTPException) as exc:
        get_current_user(x_api_key=None, authorization=None, settings=settings)
    assert exc.value.status_code == 401


def test_auth_enabled_valid_admin_key():
    settings = Settings()
    settings.auth_enabled = True
    settings.admin_api_key = "secret-adm"
    user = get_current_user(x_api_key="secret-adm", settings=settings)
    assert user.role == Role.ADMIN
    assert user.user_id == "admin-1"


def test_auth_enabled_valid_bearer_token():
    settings = Settings()
    settings.auth_enabled = True
    settings.engineer_api_key = "eng-token"
    user = get_current_user(authorization="Bearer eng-token", settings=settings)
    assert user.role == Role.ENGINEER


def test_auth_enabled_invalid_token_raises_403():
    settings = Settings()
    settings.auth_enabled = True
    with pytest.raises(HTTPException) as exc:
        get_current_user(x_api_key="wrong-key", settings=settings)
    assert exc.value.status_code == 403


def test_require_role_hierarchy():
    admin = AuthUser(user_id="1", tenant_id="t", role=Role.ADMIN)
    eng = AuthUser(user_id="2", tenant_id="t", role=Role.ENGINEER)
    auditor = AuthUser(user_id="3", tenant_id="t", role=Role.AUDITOR)

    # Admin passes all
    assert require_role(Role.ADMIN)(admin) == admin
    assert require_role(Role.ENGINEER)(admin) == admin
    assert require_role(Role.AUDITOR)(admin) == admin

    # Engineer passes engineer and auditor
    assert require_role(Role.ENGINEER)(eng) == eng
    assert require_role(Role.AUDITOR)(eng) == eng
    with pytest.raises(HTTPException) as exc:
        require_role(Role.ADMIN)(eng)
    assert exc.value.status_code == 403

    # Auditor only passes auditor
    assert require_role(Role.AUDITOR)(auditor) == auditor
    with pytest.raises(HTTPException):
        require_role(Role.ENGINEER)(auditor)
