from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)


def test_me_endpoint_without_token():
    response = client.get("/me")
    assert response.status_code == 401
    assert "Missing authentication credentials" in response.json()["detail"]


def test_me_endpoint_with_invalid_token():
    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Token expired")):
        response = client.get("/me", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]


def test_me_endpoint_with_valid_token():
    fake_decoded = {
        "uid": "test-uid-123",
        "email": "test@vixenone.app",
        "name": "Test User",
    }
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_decoded):
        response = client.get("/me", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["uid"] == "test-uid-123"
        assert data["email"] == "test@vixenone.app"
        assert data["display_name"] == "Test User"
