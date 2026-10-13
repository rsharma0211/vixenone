import asyncio
from unittest.mock import patch
import uuid
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session
from app.main import app
from app.models.user import User

client = TestClient(app)


def fake_firebase_token(uid: str, email: str = "test@vixenone.app", name: str = "Test User"):
    return {
        "uid": uid,
        "email": email,
        "name": name,
    }


def test_first_call_creates_profile():
    test_uid = f"uid-first-call-{uuid.uuid4().hex}"
    token_payload = fake_firebase_token(uid=test_uid, email="first@vixenone.app", name="First User")

    with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
        response = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "first@vixenone.app"
        assert data["display_name"] == "First User"
        assert data["role"] == "facilities_manager"
        assert "id" in data


def test_first_call_fallback_display_name():
    test_uid = f"uid-fallback-{uuid.uuid4().hex}"
    token_payload = {
        "uid": test_uid,
        "email": "priya.sharma@vixenone.app",
        "name": None,
    }

    with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
        response = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "priya.sharma@vixenone.app"
        assert data["display_name"] == "priya.sharma"
        assert data["role"] == "facilities_manager"


def test_second_call_returns_same_row():
    test_uid = f"uid-second-call-{uuid.uuid4().hex}"
    token_payload = fake_firebase_token(uid=test_uid, email="second@vixenone.app", name="Second User")

    with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
        res1 = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert res1.status_code == 200
        user1 = res1.json()

        res2 = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert res2.status_code == 200
        user2 = res2.json()

        assert user1["id"] == user2["id"]
        assert user1["email"] == user2["email"]


@pytest.mark.asyncio
async def test_concurrent_first_calls_create_one_row():
    test_uid = f"uid-concurrent-{uuid.uuid4().hex}"
    token_payload = fake_firebase_token(uid=test_uid, email="concurrent@vixenone.app", name="Concurrent User")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
            # Fire two concurrent first calls
            res1, res2 = await asyncio.gather(
                ac.get("/api/me", headers={"Authorization": "Bearer valid_token"}),
                ac.get("/api/me", headers={"Authorization": "Bearer valid_token"}),
            )

            assert res1.status_code == 200
            assert res2.status_code == 200
            data1 = res1.json()
            data2 = res2.json()

            assert data1["id"] == data2["id"]
            assert data1["role"] == "facilities_manager"
            assert data2["role"] == "facilities_manager"

    # Verify exactly one row in PostgreSQL
    async with async_session() as session:
        stmt = select(User).where(User.firebase_uid == test_uid)
        result = await session.execute(stmt)
        users = result.scalars().all()
        assert len(users) == 1
        assert str(users[0].id) == data1["id"]


def test_put_updates_role():
    test_uid = f"uid-put-role-{uuid.uuid4().hex}"
    token_payload = fake_firebase_token(uid=test_uid, email="roleuser@vixenone.app", name="Role User")

    with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
        # Initial profile creation
        res = client.get("/api/me", headers={"Authorization": "Bearer valid_token"})
        assert res.status_code == 200
        assert res.json()["role"] == "facilities_manager"

        # Update to procurement
        put_res = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"role": "procurement"},
        )
        assert put_res.status_code == 200
        assert put_res.json()["role"] == "procurement"
        assert put_res.json()["display_name"] == "Role User"

        # Update to approver and change display name
        put_res2 = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"role": "approver", "display_name": "Approver User"},
        )
        assert put_res2.status_code == 200
        assert put_res2.json()["role"] == "approver"
        assert put_res2.json()["display_name"] == "Approver User"


def test_put_invalid_role_returns_422():
    uid = "test-uid-invalid-role"
    token_payload = fake_firebase_token(uid=uid)

    with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
        res = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"role": "invalid_role"},
        )
        assert res.status_code == 422

        res2 = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"role": "admin"},
        )
        assert res2.status_code == 422


def test_put_empty_name_returns_422():
    uid = "test-uid-empty-name"
    token_payload = fake_firebase_token(uid=uid)

    with patch("firebase_admin.auth.verify_id_token", return_value=token_payload):
        res1 = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"display_name": ""},
        )
        assert res1.status_code == 422

        res2 = client.put(
            "/api/me",
            headers={"Authorization": "Bearer valid_token"},
            json={"display_name": "   "},
        )
        assert res2.status_code == 422


def test_no_token_returns_401():
    res_get = client.get("/api/me")
    assert res_get.status_code == 401

    res_put = client.put("/api/me", json={"display_name": "Test"})
    assert res_put.status_code == 401


def test_bare_me_returns_404():
    res_get_no_token = client.get("/me")
    assert res_get_no_token.status_code == 404

    fake_token = fake_firebase_token("uid-404-check")
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token):
        res_get = client.get("/me", headers={"Authorization": "Bearer valid_token"})
        assert res_get.status_code == 404

        res_put = client.put("/me", headers={"Authorization": "Bearer valid_token"}, json={"role": "procurement"})
        assert res_put.status_code == 404
