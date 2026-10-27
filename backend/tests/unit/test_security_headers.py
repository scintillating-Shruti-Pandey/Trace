"""Unit tests for enterprise security headers and endpoint RBAC protection."""

from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import AuthUser, Role, require_role
from app.config import Settings
from app.main import create_app


def test_security_headers_present():
    app = create_app(Settings())
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"


def test_rbac_endpoint_access_control():
    settings = Settings()
    settings.auth_enabled = True
    settings.admin_api_key = "test-adm-key"
    settings.engineer_api_key = "test-eng-key"
    settings.auditor_api_key = "test-audit-key"
    settings.ingest_enabled = True

    app = create_app(settings)
    client = TestClient(app)

    # Ingest requires ADMIN:
    # 1. Missing auth -> 401
    resp_no_auth = client.post("/api/v1/ingest", json={"path": "x.mp4", "kind": "video", "title": "t", "source_uri": "u", "license": "l", "equipment_family": "hydraulic"})
    assert resp_no_auth.status_code == 401

    # 2. Engineer key trying to ingest -> 403 Forbidden
    resp_eng = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": "test-eng-key"},
        json={"path": "x.mp4", "kind": "video", "title": "t", "source_uri": "u", "license": "l", "equipment_family": "hydraulic"},
    )
    assert resp_eng.status_code == 403

    # 3. Healthz remains public -> 200
    assert client.get("/healthz").status_code == 200
