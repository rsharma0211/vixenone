from unittest.mock import patch
import uuid
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def fake_token(uid: str, email: str = "user@vixenone.app"):
    return {"uid": uid, "email": email, "name": "Test User"}


def test_criteria_read_or_create_defaults():
    uid = f"uid-crit-new-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 5
        keys = [item["builtin_key"] for item in items]
        assert keys == [
            "mandatory_compliance",
            "service_coverage",
            "cost_comparability",
            "sla_operational",
            "unresolved_risks",
        ]
        total_weight = sum(item["weight"] for item in items)
        assert total_weight == 100


def test_put_criteria_total_not_100_rejected():
    uid = f"uid-crit-tot-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        criteria = get_resp.json()

        # Change weight so sum != 100
        criteria[0]["weight"] = 50  # sum becomes 115
        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp.status_code == 422
        assert "must equal 100" in put_resp.json()["detail"]


def test_put_criteria_delete_builtin_rejected():
    uid = f"uid-crit-delb-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        criteria = get_resp.json()

        # Remove 1 built-in and adjust weight on another
        del criteria[0]
        criteria[0]["weight"] += 35
        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp.status_code == 422
        assert "All 5 built-in criteria must be present" in put_resp.json()["detail"]


def test_put_criteria_edit_builtin_guidance_or_name_rejected():
    uid = f"uid-crit-editb-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        criteria = get_resp.json()

        # Try changing name
        criteria[0]["name"] = "Modified Mandatory Name"
        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp.status_code == 422
        assert "name cannot be modified" in put_resp.json()["detail"]

        # Restore name, try changing guidance
        criteria[0]["name"] = "Mandatory compliance"
        criteria[0]["guidance"] = "Changed guidance text that is long enough to pass standard length validation"
        put_resp2 = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp2.status_code == 422
        assert "guidance cannot be modified" in put_resp2.json()["detail"]


def test_put_criteria_eleven_custom_rejected():
    uid = f"uid-crit-11custom-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        criteria = get_resp.json()

        # Set built-in weights to 0 except one with 100
        for c in criteria:
            c["weight"] = 0
        criteria[0]["weight"] = 100

        # Add 11 custom criteria
        for i in range(11):
            criteria.append({
                "kind": "custom",
                "name": f"Custom Criterion {i}",
                "guidance": "Detailed guidance text for custom criterion with enough characters",
                "weight": 0,
                "position": 5 + i,
            })

        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp.status_code == 422
        assert "Maximum 10 custom criteria allowed" in put_resp.json()["detail"]


def test_put_criteria_duplicate_name_case_insensitive_rejected():
    uid = f"uid-crit-dupname-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        criteria = get_resp.json()

        # Add custom criterion that has same name as a built-in (different case)
        criteria.append({
            "kind": "custom",
            "name": "mandatory compliance",
            "guidance": "Some custom guidance text with at least twenty characters here",
            "weight": 0,
            "position": 5,
        })
        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp.status_code == 422
        assert "Duplicate criterion name" in put_resp.json()["detail"]


def test_failed_put_leaves_data_unchanged():
    uid = f"uid-crit-atomic-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        original_data = get_resp.json()

        # Send invalid payload
        bad_payload = [dict(c) for c in original_data]
        bad_payload[0]["weight"] = 99  # sum != 100
        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=bad_payload)
        assert put_resp.status_code == 422

        # Check DB data is unchanged
        refetch_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        assert refetch_resp.json() == original_data


def test_deleting_custom_criterion_preserves_evaluation_snapshot_and_results():
    uid = f"uid-crit-snap-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        # 1. Get initial criteria
        get_resp = client.get("/api/criteria", headers={"Authorization": "Bearer token"})
        criteria = get_resp.json()

        # 2. Add 1 custom criterion
        criteria[0]["weight"] -= 10
        criteria.append({
            "kind": "custom",
            "name": "Safety Protocols",
            "guidance": "Detailed review of safety training and background certifications",
            "weight": 10,
            "position": 5,
        })
        put_resp = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=criteria)
        assert put_resp.status_code == 200
        updated_criteria = put_resp.json()
        custom_crit = next(c for c in updated_criteria if c["name"] == "Safety Protocols")

        # 3. Create an evaluation with criteria snapshot
        eval_resp = client.post(
            "/api/evaluations",
            headers={"Authorization": "Bearer token"},
            json={
                "title": "Safety AMC Review",
                "category": "Facilities / Safety",
                "vendor_names": ["Vendor Alpha", "Vendor Beta"],
            },
        )
        assert eval_resp.status_code == 201
        eval_id = eval_resp.json()["id"]

        # Simulate analysis snapshot on evaluation
        from app.models.evaluation import Evaluation
        from app.core.database import async_session
        import asyncio
        async def set_snapshot():
            async with async_session() as s:
                e = await s.get(Evaluation, uuid.UUID(eval_id))
                e.criteria_snapshot = [
                    {"key": f"custom:{custom_crit['id']}", "kind": "custom", "name": "Safety Protocols", "guidance": custom_crit["guidance"], "weight": 10},
                    {"key": "mandatory_compliance", "kind": "builtin", "name": "Mandatory compliance", "guidance": "guidance", "weight": 90},
                ]
                e.status = "analysed"
                await s.commit()
        asyncio.run(set_snapshot())

        # 4. Now delete custom criterion from user criteria
        reset_criteria = [c for c in updated_criteria if c["name"] != "Safety Protocols"]
        reset_criteria[0]["weight"] += 10
        put_resp2 = client.put("/api/criteria", headers={"Authorization": "Bearer token"}, json=reset_criteria)
        assert put_resp2.status_code == 200

        # 5. Check evaluation detail and results still have the snapshot!
        detail_resp = client.get(f"/api/evaluations/{eval_id}", headers={"Authorization": "Bearer token"})
        assert detail_resp.status_code == 200
        snap = detail_resp.json()["criteria_snapshot"]
        assert len(snap) == 2
        assert snap[0]["key"] == f"custom:{custom_crit['id']}"
