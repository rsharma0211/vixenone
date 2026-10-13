import io
from unittest.mock import patch
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.evaluation import Evaluation, Vendor, Requirement, Document
from app.core.database import async_session
import asyncio

client = TestClient(app)


def fake_token(uid: str, email: str = "eval_user@vixenone.app"):
    return {"uid": uid, "email": email, "name": "Eval User"}


def test_cross_user_404_isolation_on_all_endpoints():
    user1_uid = f"uid-user1-{uuid.uuid4().hex}"
    user2_uid = f"uid-user2-{uuid.uuid4().hex}"

    # User 1 creates an evaluation
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(user1_uid)):
        create_resp = client.post(
            "/api/evaluations",
            headers={"Authorization": "Bearer token1"},
            json={
                "title": "Confidential RFP",
                "category": "Facilities",
                "vendor_names": ["Vendor A", "Vendor B"],
            },
        )
        assert create_resp.status_code == 201
        eval_id = create_resp.json()["id"]

    # User 2 tries to access User 1's evaluation on every endpoint -> 404
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(user2_uid)):
        auth2 = {"Authorization": "Bearer token2"}

        assert client.get(f"/api/evaluations/{eval_id}", headers=auth2).status_code == 404
        assert client.patch(f"/api/evaluations/{eval_id}", headers=auth2, json={"title": "Hacked"}).status_code == 404
        assert client.delete(f"/api/evaluations/{eval_id}", headers=auth2).status_code == 404
        assert client.get(f"/api/evaluations/{eval_id}/requirements", headers=auth2).status_code == 404
        assert client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth2, json=[]).status_code == 404
        assert client.get(f"/api/evaluations/{eval_id}/jobs/latest", headers=auth2).status_code == 404
        assert client.get(f"/api/evaluations/{eval_id}/results", headers=auth2).status_code == 404

        # Document endpoints
        fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        files = {"file": ("test.pdf", fake_pdf, "application/pdf")}
        data = {"kind": "requirements"}
        assert client.post(f"/api/evaluations/{eval_id}/documents", headers=auth2, files=files, data=data).status_code == 404
        assert client.delete(f"/api/evaluations/{eval_id}/documents/{uuid.uuid4()}", headers=auth2).status_code == 404


def test_create_evaluation_validation():
    uid = f"uid-eval-val-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        # Less than 2 vendors -> 422
        r1 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP", "category": "Facilities", "vendor_names": ["Vendor A"]},
        )
        assert r1.status_code == 422

        # More than 3 vendors -> 422
        r2 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP", "category": "Facilities", "vendor_names": ["A", "B", "C", "D"]},
        )
        assert r2.status_code == 422

        # Duplicate vendors -> 422
        r3 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP", "category": "Facilities", "vendor_names": ["Vendor A", "vendor a"]},
        )
        assert r3.status_code == 422

        # Valid 2 vendors
        r4 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP", "category": "Facilities", "vendor_names": ["Vendor A", "Vendor B"]},
        )
        assert r4.status_code == 201
        assert r4.json()["status"] == "draft"
        assert len(r4.json()["vendors"]) == 2


def test_requirements_put_on_analysed_evaluation_marks_stale():
    uid = f"uid-req-stale-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        create_resp = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP", "category": "Facilities", "vendor_names": ["Vendor A", "Vendor B"]},
        )
        eval_id = create_resp.json()["id"]

        # Manually set status to analysed in DB
        async def mark_analysed():
            async with async_session() as s:
                e = await s.get(Evaluation, uuid.UUID(eval_id))
                e.status = "analysed"
                await s.commit()
        asyncio.run(mark_analysed())

        # Check status is analysed
        detail1 = client.get(f"/api/evaluations/{eval_id}", headers=auth).json()
        assert detail1["status"] == "analysed"

        # PUT new requirements
        new_reqs = [
            {
                "code": "REQ-01",
                "text": "Daily floor sweeping",
                "category": "Service",
                "mandatory": True,
                "acceptance": "Daily signoff",
                "position": 0,
                "origin": "user",
            }
        ]
        put_resp = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=new_reqs)
        assert put_resp.status_code == 200
        assert len(put_resp.json()) == 1

        # Check status transitioned to stale!
        detail2 = client.get(f"/api/evaluations/{eval_id}", headers=auth).json()
        assert detail2["status"] == "stale"


def test_delete_cascades_rows_and_files():
    uid = f"uid-del-cascade-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        create_resp = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Cascade Test", "category": "Facilities", "vendor_names": ["Vendor A", "Vendor B"]},
        )
        eval_id = create_resp.json()["id"]

        # Upload a minimal valid PDF
        import pdfplumber
        # Generate minimal valid single-page PDF with pdfplumber / raw PDF syntax
        raw_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n193\n%%EOF"
        )
        files = {"file": ("test.pdf", raw_pdf, "application/pdf")}
        data = {"kind": "requirements"}
        upload_resp = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data=data)
        assert upload_resp.status_code == 200
        doc_storage_key = upload_resp.json()["storage_key"]

        from app.services.storage import get_storage
        storage = get_storage()
        import asyncio
        assert asyncio.run(storage.exists(doc_storage_key)) is True

        # Delete evaluation
        del_resp = client.delete(f"/api/evaluations/{eval_id}", headers=auth)
        assert del_resp.status_code == 204

        # Check file removed from storage
        assert asyncio.run(storage.exists(doc_storage_key)) is False

        # Check DB rows removed
        assert client.get(f"/api/evaluations/{eval_id}", headers=auth).status_code == 404


def test_requirements_put_validation_and_atomicity():
    uid = f"uid-req-val-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        create_resp = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Validation RFP", "category": "Facilities", "vendor_names": ["Vendor A", "Vendor B"]},
        )
        assert create_resp.status_code == 201
        eval_id = create_resp.json()["id"]

        # 1. Valid list saves and trims fields
        valid_initial = [
            {
                "code": "  REQ-01  ",
                "text": "  Trained guards on duty 24x7.  ",
                "category": "  Security coverage  ",
                "mandatory": True,
                "acceptance": "  Duty roster attached.  ",
                "position": 0,
                "origin": "user",
            },
            {
                "code": "REQ-02",
                "text": "One supervisor on site per shift.",
                "category": "Supervision",
                "mandatory": False,
                "acceptance": "Supervisor named.",
                "position": 1,
                "origin": "extracted",
            },
        ]
        save_resp = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=valid_initial)
        assert save_resp.status_code == 200
        saved_items = save_resp.json()
        assert len(saved_items) == 2
        assert saved_items[0]["code"] == "REQ-01"
        assert saved_items[0]["text"] == "Trained guards on duty 24x7."
        assert saved_items[0]["category"] == "Security coverage"
        assert saved_items[0]["acceptance"] == "Duty roster attached."

        # 2. Empty code -> 422
        empty_code_payload = [
            {
                "code": "   ",
                "text": "Valid text",
                "category": "Ops",
                "mandatory": True,
                "acceptance": "Check",
                "position": 0,
                "origin": "user",
            }
        ]
        r_empty_code = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=empty_code_payload)
        assert r_empty_code.status_code == 422

        # 3. Whitespace-only text -> 422
        ws_text_payload = [
            {
                "code": "REQ-01",
                "text": "   \t\n  ",
                "category": "Ops",
                "mandatory": True,
                "acceptance": "Check",
                "position": 0,
                "origin": "user",
            }
        ]
        r_ws_text = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=ws_text_payload)
        assert r_ws_text.status_code == 422

        # 4. Length violations (code > 20, text > 1000, category > 80, acceptance > 1000) -> 422
        for bad_field, bad_val in [
            ("code", "R" * 21),
            ("text", "T" * 1001),
            ("category", "C" * 81),
            ("acceptance", "A" * 1001),
        ]:
            item = {
                "code": "REQ-01",
                "text": "Valid text",
                "category": "Ops",
                "mandatory": True,
                "acceptance": "Check",
                "position": 0,
                "origin": "user",
            }
            item[bad_field] = bad_val
            r_len = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=[item])
            assert r_len.status_code == 422

        # 5. Duplicate codes differing only by case -> 422
        dup_code_payload = [
            {
                "code": "REQ-01",
                "text": "First requirement",
                "category": "Ops",
                "mandatory": True,
                "acceptance": "Check 1",
                "position": 0,
                "origin": "user",
            },
            {
                "code": "req-01",
                "text": "Second requirement with lowercase code",
                "category": "Ops",
                "mandatory": False,
                "acceptance": "Check 2",
                "position": 1,
                "origin": "user",
            },
        ]
        r_dup = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=dup_code_payload)
        assert r_dup.status_code == 422
        assert "Duplicate requirement code" in r_dup.json()["detail"]

        # 6. Failed PUT leaves list unchanged (no partial writes)
        refetched = client.get(f"/api/evaluations/{eval_id}/requirements", headers=auth).json()
        assert refetched == saved_items

