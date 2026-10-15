import uuid
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.auth import (
    create_session_token,
    verify_session_token,
    verify_admin_password,
    validate_production_auth_at_startup,
    get_configured_admin_password,
)

client = TestClient(app)

TEST_PASSWORD = "production_test_password_98765"
TEST_API_KEY = "test_api_key_secret_12345"


@pytest.fixture(autouse=True)
def setup_auth_environment(monkeypatch):
    """Configures explicit test credentials and enables strict authentication for this test module."""
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", TEST_PASSWORD)
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    monkeypatch.setattr(settings, "TEST_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "TEST_MODE", False)


# -------------------------------------------------------------------------
# 1. Unauthorized Access Rejected (Requirement 2)
# -------------------------------------------------------------------------
def test_unauthorized_requests_rejected_across_all_protected_routes():
    dummy_uuid = str(uuid.uuid4())
    protected_endpoints = [
        ("GET", "/api/monitors"),
        ("POST", "/api/monitors"),
        ("GET", f"/api/monitors/{dummy_uuid}"),
        ("PATCH", f"/api/monitors/{dummy_uuid}"),
        ("DELETE", f"/api/monitors/{dummy_uuid}"),
        ("GET", f"/api/monitors/{dummy_uuid}/checks"),
        ("POST", f"/api/monitors/{dummy_uuid}/checks"),
        ("GET", f"/api/checks/{dummy_uuid}"),
        ("GET", f"/api/monitors/{dummy_uuid}/versions"),
        ("GET", f"/api/monitors/{dummy_uuid}/versions/{dummy_uuid}"),
        ("GET", f"/api/versions/{dummy_uuid}/screenshot"),
        ("GET", f"/api/monitors/{dummy_uuid}/compare?from={dummy_uuid}&to={dummy_uuid}"),
        ("GET", f"/api/monitors/{dummy_uuid}/picker"),
        ("PUT", f"/api/monitors/{dummy_uuid}/rules"),
        ("GET", "/api/settings/notifications"),
        ("PUT", "/api/settings/notifications/discord"),
        ("POST", "/api/settings/notifications/discord/test"),
        ("GET", "/api/notifications/outbox"),
        ("GET", f"/api/monitors/{dummy_uuid}/channels"),
        ("GET", "/api/activity"),
    ]

    for method, endpoint in protected_endpoints:
        if method == "GET":
            res = client.get(endpoint)
        elif method == "POST":
            res = client.post(endpoint, json={})
        elif method == "PUT":
            res = client.put(endpoint, json={})
        elif method == "PATCH":
            res = client.patch(endpoint, json={})
        elif method == "DELETE":
            res = client.delete(endpoint)
        else:
            continue

        assert res.status_code == 401, f"Expected 401 for {method} {endpoint}, got {res.status_code}"
        assert res.headers.get("WWW-Authenticate") == "Bearer"
        data = res.json()
        assert data["detail"]["error"]["code"] == "UNAUTHORIZED"


# -------------------------------------------------------------------------
# 2. Public Health & Root Endpoints (Requirement 7)
# -------------------------------------------------------------------------
def test_public_health_and_root_endpoints_accessible_without_auth():
    # 1. Health endpoint must be accessible without credentials
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert "status" in health_data
    assert "database" in health_data
    assert "redis" in health_data

    # Must be free of sensitive credentials
    assert TEST_PASSWORD not in str(health_data)
    assert TEST_API_KEY not in str(health_data)
    assert "password" not in str(health_data).lower()
    assert "postgres:" not in str(health_data).lower()

    # 2. Root endpoint
    res_root = client.get("/")
    assert res_root.status_code == 200
    root_data = res_root.json()
    assert root_data["status"] == "active"
    assert TEST_PASSWORD not in str(root_data)


# -------------------------------------------------------------------------
# 3. Authentication Login Flow (Requirement 3 & 4)
# -------------------------------------------------------------------------
def test_auth_login_invalid_password_rejected():
    res = client.post("/api/auth/login", json={"password": "wrong_password_attempt"})
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


def test_auth_login_valid_password_issues_session_token():
    res = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert "expires_at" in data
    assert data["user"] == "admin"

    token = data["token"]
    assert "." in token

    # Verify session token validity
    payload = verify_session_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["exp"] > time.time()


# -------------------------------------------------------------------------
# 4. Authorized Access with Bearer Token (Requirement 2 & 4)
# -------------------------------------------------------------------------
def test_authorized_access_with_bearer_token():
    # Obtain token
    login_res = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    token = login_res.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Protected GET /api/monitors must succeed
    res_monitors = client.get("/api/monitors", headers=headers)
    assert res_monitors.status_code == 200
    assert "items" in res_monitors.json()

    # Protected GET /api/settings/notifications must succeed
    res_settings = client.get("/api/settings/notifications", headers=headers)
    assert res_settings.status_code == 200

    # Protected GET /api/activity must succeed
    res_activity = client.get("/api/activity", headers=headers)
    assert res_activity.status_code == 200

    # GET /api/auth/status must report authenticated
    res_status = client.get("/api/auth/status", headers=headers)
    assert res_status.status_code == 200
    assert res_status.json()["authenticated"] is True
    assert res_status.json()["user"] == "admin"


# -------------------------------------------------------------------------
# 5. Authorized Access with X-API-Key Header
# -------------------------------------------------------------------------
def test_authorized_access_with_x_api_key_header():
    headers = {"X-API-Key": TEST_API_KEY}

    res = client.get("/api/monitors", headers=headers)
    assert res.status_code == 200
    assert "items" in res.json()

    # Invalid API key rejected
    res_bad = client.get("/api/monitors", headers={"X-API-Key": "bad_key_123"})
    assert res_bad.status_code == 401


# -------------------------------------------------------------------------
# 6. Query Parameter Token for <img> Media Requests
# -------------------------------------------------------------------------
def test_authorized_media_request_with_query_param_token():
    token, _ = create_session_token("admin")
    dummy_version_id = str(uuid.uuid4())

    # Without token -> 401
    res_no_auth = client.get(f"/api/versions/{dummy_version_id}/screenshot")
    assert res_no_auth.status_code == 401

    # With query param token -> auth passes (fails with 404 because dummy version doesn't exist, not 401)
    res_with_auth = client.get(f"/api/versions/{dummy_version_id}/screenshot?token={token}")
    assert res_with_auth.status_code == 404, f"Expected 404 (authorized but not found), got {res_with_auth.status_code}"


# -------------------------------------------------------------------------
# 7. Forged and Expired Tokens Rejected
# -------------------------------------------------------------------------
def test_forged_and_expired_tokens_rejected():
    # 1. Tampered payload
    token, _ = create_session_token("admin")
    parts = token.split(".")
    tampered_token = f"eyJhbGciOiJIUzI1NiJ9.{parts[1]}"
    res_tampered = client.get("/api/monitors", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401

    # 2. Tampered signature
    tampered_sig = f"{parts[0]}.badsignature12345"
    res_bad_sig = client.get("/api/monitors", headers={"Authorization": f"Bearer {tampered_sig}"})
    assert res_bad_sig.status_code == 401

    # 3. Expired token
    expired_token, _ = create_session_token("admin", expires_in_seconds=-3600)
    res_expired = client.get("/api/monitors", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401


# -------------------------------------------------------------------------
# 8. Secret Non-Disclosure (Requirement 8)
# -------------------------------------------------------------------------
def test_secret_non_disclosure():
    # Ensure password or API key is never leaked in 401 error payloads
    res_401 = client.get("/api/monitors")
    err_text = res_401.text
    assert TEST_PASSWORD not in err_text
    assert TEST_API_KEY not in err_text

    # Ensure login error doesn't echo password
    res_login_err = client.post("/api/auth/login", json={"password": "my_secret_typo_123"})
    assert "my_secret_typo_123" not in res_login_err.text


# -------------------------------------------------------------------------
# 9. Production Mode Safeguards (Requirement 6)
# -------------------------------------------------------------------------
def test_production_mode_safeguards(monkeypatch):
    # 1. In production, missing ADMIN_PASSWORD raises RuntimeError on startup
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)

    with pytest.raises(RuntimeError) as exc:
        validate_production_auth_at_startup()
    assert "CRITICAL CONFIGURATION ERROR" in str(exc.value)
    assert "ADMIN_PASSWORD is required in production" in str(exc.value)

    # 2. In production, TEST_MODE is automatically forced to False
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "prod_pw_123")
    monkeypatch.setattr(settings, "TEST_MODE", True)
    validate_production_auth_at_startup()
    assert settings.TEST_MODE is False
