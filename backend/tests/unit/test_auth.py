import logging
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.auth import init_firebase
from app.core.config import Settings
from app.main import app

client = TestClient(app)


def test_bare_me_endpoint_returns_404():
    response = client.get("/me")
    assert response.status_code == 404
    put_response = client.put("/me")
    assert put_response.status_code == 404


def test_api_me_endpoint_without_token():
    response = client.get("/api/me")
    assert response.status_code == 401
    assert "Missing authentication credentials" in response.json()["detail"]


def test_api_me_endpoint_with_invalid_token():
    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Token expired")):
        response = client.get("/api/me", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]


def test_api_me_endpoint_with_valid_token():
    fake_decoded = {
        "uid": "test-uid-auth-check",
        "email": "authcheck@vixenone.app",
        "name": "Auth Check User",
    }
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_decoded):
        response = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "authcheck@vixenone.app"
        assert data["display_name"] == "Auth Check User"
        assert data["role"] == "facilities_manager"
        assert "id" in data


def test_init_firebase_emulator_mode(caplog):
    test_settings = Settings(
        ENV="development",
        FIREBASE_PROJECT_ID="demo-vixenone",
        FIREBASE_AUTH_EMULATOR_HOST="localhost:9099",
    )
    with patch("firebase_admin.get_app", side_effect=ValueError("No app")), \
         patch("firebase_admin.initialize_app") as mock_init:
        with caplog.at_level(logging.INFO):
            init_firebase(test_settings)
            mock_init.assert_called_once_with(options={"projectId": "demo-vixenone"})
            assert "credential" not in mock_init.call_args.kwargs
            assert "emulator mode" in caplog.text
            assert "demo-vixenone" in caplog.text


def test_init_firebase_adc_mode(caplog):
    test_settings = Settings(
        ENV="production",
        FIREBASE_PROJECT_ID="prod-vixenone",
        FIREBASE_AUTH_EMULATOR_HOST=None,
    )
    with patch("firebase_admin.get_app", side_effect=ValueError("No app")), \
         patch("firebase_admin.initialize_app") as mock_init:
        with caplog.at_level(logging.INFO):
            init_firebase(test_settings)
            mock_init.assert_called_once_with(options={"projectId": "prod-vixenone"})
            assert "credential" not in mock_init.call_args.kwargs
            assert "ADC mode" in caplog.text
            assert "prod-vixenone" in caplog.text


def test_init_firebase_production_emulator_failure():
    test_settings = Settings(
        ENV="production",
        FIREBASE_PROJECT_ID="prod-vixenone",
        FIREBASE_AUTH_EMULATOR_HOST="localhost:9099",
    )
    with pytest.raises(ValueError, match="production"):
        init_firebase(test_settings)


def test_startup_lifespan_failure_in_production():
    prod_settings = Settings(
        ENV="production",
        FIREBASE_PROJECT_ID="prod-vixenone",
        FIREBASE_AUTH_EMULATOR_HOST="localhost:9099",
    )
    with patch("app.main.settings", prod_settings):
        with pytest.raises(ValueError, match="production"):
            with TestClient(app):
                pass
