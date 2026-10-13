from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_no_store_header_on_protected_endpoint_unauthorized():
    # Protected endpoint without credentials returns 401 and no-store header
    resp = client.get("/api/me")
    assert resp.status_code == 401
    cache_control = resp.headers.get("Cache-Control")
    assert cache_control is not None
    assert "no-store" in cache_control


def test_no_store_header_on_protected_endpoint_authorized():
    # Protected endpoint with valid token returns 200 and no-store header
    fake_token = {
        "uid": "test-uid-cache-check",
        "email": "cache@vixenone.app",
        "name": "Cache Check",
    }
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token):
        resp = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert resp.status_code == 200
        cache_control = resp.headers.get("Cache-Control")
        assert cache_control is not None
        assert "no-store" in cache_control


def test_no_store_header_on_error_response_not_found():
    # 404 Not Found error response has no-store header
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    cache_control = resp.headers.get("Cache-Control")
    assert cache_control is not None
    assert "no-store" in cache_control


def test_no_store_header_on_error_response_validation_error():
    # 422 Validation error response has no-store header
    fake_token = {
        "uid": "test-uid-validation-check",
        "email": "validation@vixenone.app",
        "name": "Validation Check",
    }
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token):
        resp = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"role": "invalid_role"},
        )
        assert resp.status_code == 422
        cache_control = resp.headers.get("Cache-Control")
        assert cache_control is not None
        assert "no-store" in cache_control
