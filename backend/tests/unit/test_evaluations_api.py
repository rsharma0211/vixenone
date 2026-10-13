from unittest.mock import patch
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.models.evaluation import Evaluation, Document
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

        # Vendor endpoints (cross-user -> 404 on all three)
        v1_id = create_resp.json()["vendors"][0]["id"]
        assert client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth2, json={"name": "Intruder"}).status_code == 404
        assert client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth2, json={"name": "Intruder"}).status_code == 404
        assert client.delete(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth2).status_code == 404


def test_create_evaluation_validation():
    uid = f"uid-eval-val-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        # Create with 0 vendors (omitted vendor_names) -> 201 draft
        r0 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Two-Step RFP", "category": "Facilities"},
        )
        assert r0.status_code == 201
        assert r0.json()["status"] == "draft"
        assert r0.json()["vendors"] == []

        # Create with explicit empty vendor_names and optional location_id -> 201 draft
        r0_empty = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Two-Step RFP Mumbai", "category": "Facilities", "location_id": None, "vendor_names": []},
        )
        assert r0_empty.status_code == 201
        assert r0_empty.json()["status"] == "draft"
        assert r0_empty.json()["location"] is None
        assert r0_empty.json()["vendors"] == []

        # Create with 1 vendor -> 201 draft
        r1 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP", "category": "Facilities", "vendor_names": ["Vendor A"]},
        )
        assert r1.status_code == 201
        assert r1.json()["status"] == "draft"
        assert len(r1.json()["vendors"]) == 1

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

        # Valid 2 and 3 vendors still work
        r4 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP 2", "category": "Facilities", "vendor_names": ["Vendor A", "Vendor B"]},
        )
        assert r4.status_code == 201
        assert r4.json()["status"] == "draft"
        assert len(r4.json()["vendors"]) == 2

        r5 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "RFP 3", "category": "Facilities", "vendor_names": ["Vendor A", "Vendor B", "Vendor C"]},
        )
        assert r5.status_code == 201
        assert r5.json()["status"] == "draft"
        assert len(r5.json()["vendors"]) == 3


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

        # Generate minimal valid single-page PDF with raw PDF syntax
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


def test_vendor_add_validation_and_max_3():
    uid = f"uid-vendor-add-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        # Create with 0 vendors -> 201 draft
        ev = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Zero Vendor Eval", "category": "Facilities"},
        ).json()
        eval_id = ev["id"]
        assert ev["status"] == "draft"
        assert ev["vendors"] == []

        # Empty / whitespace / >80 chars -> 422
        assert client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": ""}).status_code == 422
        assert client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "   \t  "}).status_code == 422
        assert client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "V" * 81}).status_code == 422

        # Add 1st vendor (trimmed) -> 201 at position 0
        r1 = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "  Alpha Services  "})
        assert r1.status_code == 201
        assert r1.json()["name"] == "Alpha Services"
        assert r1.json()["position"] == 0

        # Duplicate name (case differs) -> 422
        r_dup = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "alpha services"})
        assert r_dup.status_code == 422

        # Add 2nd and 3rd vendors -> 201 at positions 1 and 2
        r2 = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "Beta Corp"})
        assert r2.status_code == 201
        assert r2.json()["position"] == 1

        r3 = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "Gamma Ltd"})
        assert r3.status_code == 201
        assert r3.json()["position"] == 2

        # Add 4th vendor -> 422 "An evaluation can have at most 3 vendors."
        r4 = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "Delta Inc"})
        assert r4.status_code == 422
        assert r4.json()["detail"] == "An evaluation can have at most 3 vendors."


def test_vendor_rename_validation_and_preserves_status():
    uid = f"uid-vendor-rename-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        ev = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Rename Eval", "category": "Facilities", "vendor_names": ["Vendor One", "Vendor Two"]},
        ).json()
        eval_id = ev["id"]
        v1_id = ev["vendors"][0]["id"]

        # Empty / whitespace / >80 chars -> 422
        assert client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth, json={"name": ""}).status_code == 422
        assert client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth, json={"name": "   "}).status_code == 422
        assert client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth, json={"name": "N" * 81}).status_code == 422

        # Duplicate of Vendor Two (case-insensitive) -> 422
        r_dup = client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth, json={"name": "vendor two"})
        assert r_dup.status_code == 422

        # Rename on analysed evaluation keeps status 'analysed'
        async def set_status(st: str):
            async with async_session() as s:
                e = await s.get(Evaluation, uuid.UUID(eval_id))
                e.status = st
                await s.commit()

        for st in ("draft", "requirements_review", "analysed", "stale"):
            asyncio.run(set_status(st))
            new_name = f"  Vendor One ({st})  "
            r_ok = client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth, json={"name": new_name})
            assert r_ok.status_code == 200
            assert r_ok.json()["name"] == new_name.strip()
            detail = client.get(f"/api/evaluations/{eval_id}", headers=auth).json()
            assert detail["status"] == st


def test_vendor_delete_cascades_all_rows_and_files_and_renumbers_positions():
    from sqlalchemy import select
    from app.models.evaluation import (
        Clarification,
        CostBreakdown,
        CriterionScore,
        DocumentPage,
        Finding,
    )
    from app.services.storage import get_storage

    uid = f"uid-vendor-del-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        ev = client.post(
            "/api/evaluations",
            headers=auth,
            json={
                "title": "Vendor Cascade Eval",
                "category": "Facilities",
                "vendor_names": ["Vendor 0", "Vendor 1", "Vendor 2"],
            },
        ).json()
        eval_id = ev["id"]
        v0_id = ev["vendors"][0]["id"]
        v1_id = ev["vendors"][1]["id"]
        v2_id = ev["vendors"][2]["id"]

        raw_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n193\n%%EOF"
        )
        doc0_resp = client.post(
            f"/api/evaluations/{eval_id}/documents",
            headers=auth,
            files={"file": ("v0.pdf", raw_pdf, "application/pdf")},
            data={"kind": "proposal", "vendor_id": v0_id},
        ).json()
        doc1_resp = client.post(
            f"/api/evaluations/{eval_id}/documents",
            headers=auth,
            files={"file": ("v1.pdf", raw_pdf, "application/pdf")},
            data={"kind": "proposal", "vendor_id": v1_id},
        ).json()

        doc0_id = uuid.UUID(doc0_resp["id"])
        doc1_id = uuid.UUID(doc1_resp["id"])
        doc0_key = doc0_resp["storage_key"]
        doc1_key = doc1_resp["storage_key"]

        storage = get_storage()
        assert asyncio.run(storage.exists(doc0_key)) is True
        assert asyncio.run(storage.exists(doc1_key)) is True

        # Seed dependent rows for both v0 and v1
        async def seed_vendor_dependents():
            async with async_session() as s:
                eval_uuid = uuid.UUID(eval_id)
                for vid_str, did in [(v0_id, doc0_id), (v1_id, doc1_id)]:
                    v_uuid = uuid.UUID(vid_str)
                    s.add(DocumentPage(id=uuid.uuid4(), document_id=did, page_number=1, text="Page 1 text"))
                    s.add(
                        Finding(
                            id=uuid.uuid4(),
                            evaluation_id=eval_uuid,
                            vendor_id=v_uuid,
                            status="Compliant",
                            needs_review=False,
                            is_inference=False,
                            confidence="High",
                            evidence_quote="Page 1 text",
                            evidence_document_id=did,
                            evidence_page=1,
                            risk_types=[],
                        )
                    )
                    s.add(
                        CriterionScore(
                            id=uuid.uuid4(),
                            evaluation_id=eval_uuid,
                            vendor_id=v_uuid,
                            criterion_key="mandatory_compliance",
                            score=90,
                        )
                    )
                    s.add(
                        CostBreakdown(
                            id=uuid.uuid4(),
                            evaluation_id=eval_uuid,
                            vendor_id=v_uuid,
                            monthly_base=100000,
                            gst_18=18000,
                            monthly_total=118000,
                            included=["Staff"],
                            excluded=[],
                            optional=[],
                            unknown=[],
                        )
                    )
                    s.add(
                        Clarification(
                            id=uuid.uuid4(),
                            evaluation_id=eval_uuid,
                            vendor_id=v_uuid,
                            question="Confirm shift timings?",
                            answered=False,
                        )
                    )
                await s.commit()

        asyncio.run(seed_vendor_dependents())

        # Delete middle vendor (Vendor 1)
        del_resp = client.delete(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth)
        assert del_resp.status_code == 204

        # File for v1 removed, file for v0 retained
        assert asyncio.run(storage.exists(doc1_key)) is False
        assert asyncio.run(storage.exists(doc0_key)) is True

        # Verify all dependent rows for v1 are gone while v0's remain
        async def verify_db_rows():
            async with async_session() as s:
                v1_uuid = uuid.UUID(v1_id)
                v0_uuid = uuid.UUID(v0_id)
                assert (await s.execute(select(Document).where(Document.id == doc1_id))).scalar_one_or_none() is None
                assert (await s.execute(select(DocumentPage).where(DocumentPage.document_id == doc1_id))).scalar_one_or_none() is None
                assert (await s.execute(select(Finding).where(Finding.vendor_id == v1_uuid))).scalar_one_or_none() is None
                assert (await s.execute(select(CriterionScore).where(CriterionScore.vendor_id == v1_uuid))).scalar_one_or_none() is None
                assert (await s.execute(select(CostBreakdown).where(CostBreakdown.vendor_id == v1_uuid))).scalar_one_or_none() is None
                assert (await s.execute(select(Clarification).where(Clarification.vendor_id == v1_uuid))).scalar_one_or_none() is None

                assert (await s.execute(select(Document).where(Document.id == doc0_id))).scalar_one_or_none() is not None
                assert (await s.execute(select(DocumentPage).where(DocumentPage.document_id == doc0_id))).scalar_one_or_none() is not None
                assert (await s.execute(select(Finding).where(Finding.vendor_id == v0_uuid))).scalar_one_or_none() is not None
                assert (await s.execute(select(CriterionScore).where(CriterionScore.vendor_id == v0_uuid))).scalar_one_or_none() is not None
                assert (await s.execute(select(CostBreakdown).where(CostBreakdown.vendor_id == v0_uuid))).scalar_one_or_none() is not None
                assert (await s.execute(select(Clarification).where(Clarification.vendor_id == v0_uuid))).scalar_one_or_none() is not None

        asyncio.run(verify_db_rows())

        # Remaining vendors re-numbered without gaps (positions 0 and 1)
        detail = client.get(f"/api/evaluations/{eval_id}", headers=auth).json()
        assert [v["id"] for v in detail["vendors"]] == [v0_id, v2_id]
        assert [v["position"] for v in detail["vendors"]] == [0, 1]

        # Appending another vendor gets position 2
        r_new = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "Vendor 3"})
        assert r_new.status_code == 201
        assert r_new.json()["position"] == 2


def test_vendor_add_and_delete_on_analysed_marks_stale():
    uid = f"uid-vendor-stale-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        ev = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Stale Vendor Eval", "category": "Facilities", "vendor_names": ["V1", "V2"]},
        ).json()
        eval_id = ev["id"]

        async def set_analysed():
            async with async_session() as s:
                e = await s.get(Evaluation, uuid.UUID(eval_id))
                e.status = "analysed"
                await s.commit()

        # Add vendor on analysed -> stale
        asyncio.run(set_analysed())
        r_add = client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "V3"})
        assert r_add.status_code == 201
        v3_id = r_add.json()["id"]
        assert client.get(f"/api/evaluations/{eval_id}", headers=auth).json()["status"] == "stale"

        # Delete vendor on analysed -> stale
        asyncio.run(set_analysed())
        r_del = client.delete(f"/api/evaluations/{eval_id}/vendors/{v3_id}", headers=auth)
        assert r_del.status_code == 204
        assert client.get(f"/api/evaluations/{eval_id}", headers=auth).json()["status"] == "stale"


def test_vendor_endpoints_409_during_active_job():
    from app.models.evaluation import AnalysisJob

    uid = f"uid-vendor-409-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        ev = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Active Job Eval", "category": "Facilities", "vendor_names": ["V1", "V2"]},
        ).json()
        eval_id = ev["id"]
        v1_id = ev["vendors"][0]["id"]

        async def insert_job():
            async with async_session() as s:
                s.add(
                    AnalysisJob(
                        id=uuid.uuid4(),
                        evaluation_id=uuid.UUID(eval_id),
                        kind="extract_requirements",
                        status="extracting",
                        step_label="Reading",
                    )
                )
                await s.commit()

        asyncio.run(insert_job())

        assert client.post(f"/api/evaluations/{eval_id}/vendors", headers=auth, json={"name": "V3"}).status_code == 409
        assert client.patch(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth, json={"name": "V1 Renamed"}).status_code == 409
        assert client.delete(f"/api/evaluations/{eval_id}/vendors/{v1_id}", headers=auth).status_code == 409


