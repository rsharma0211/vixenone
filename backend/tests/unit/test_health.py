from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)


def test_health_endpoint_success():
    with patch("app.main.check_db_health", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "ok"}


def test_health_endpoint_db_failure():
    with patch("app.main.check_db_health", return_value=False):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "error"}


def test_cors_headers():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
