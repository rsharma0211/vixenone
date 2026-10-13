from unittest.mock import patch
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.database import async_session
from app.main import app
from app.models.evaluation import Evaluation
from app.models.user import User
from app.services.seed_demo import seed_demo_data
import asyncio

client = TestClient(app)


DEMO_UID = "demo-uid-vixenone"


def demo_token():
    return {
        "uid": DEMO_UID,
        "email": "demo@vixenone.app",
        "name": "Priya Sharma",
    }


@pytest.fixture(autouse=True)
def ensure_demo_seeded():
    global DEMO_UID
    async def init():
        async with async_session() as s:
            from sqlalchemy import select
            from app.models.company import Company
            user = (await s.execute(select(User).where(User.email == "demo@vixenone.app"))).scalars().first()
            if not user:
                company = Company(
                    id=uuid.UUID("00000000-0000-0000-0000-000000000099"),
                    name="Northbridge Properties Pvt Ltd",
                )
                s.add(company)
                await s.flush()
                user = User(
                    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    company_id=company.id,
                    firebase_uid="demo-uid-vixenone",
                    email="demo@vixenone.app",
                    display_name="Priya Sharma",
                )
                s.add(user)
                await s.commit()
            await seed_demo_data(s)
            return user.firebase_uid
    DEMO_UID = asyncio.run(init())


def test_demo_kpi_counts():
    with patch("firebase_admin.auth.verify_id_token", return_value=demo_token()):
        resp = client.get("/api/evaluations", headers={"Authorization": "Bearer demo"})
        assert resp.status_code == 200
        data = resp.json()
        kpis = data["kpis"]
        # Expected: 4 / 2 / 1 / 4
        assert kpis["total"] == 4, f"Expected total=4, got {kpis['total']}"
        assert kpis["needs_action"] == 2, f"Expected needs_action=2, got {kpis['needs_action']}"
        assert kpis["analysed"] == 1, f"Expected analysed=1, got {kpis['analysed']}"
        assert kpis["open_clarifications"] == 4, f"Expected open_clarifications=4, got {kpis['open_clarifications']}"


def test_demo_results_totals_and_points_raw_and_display():
    with patch("firebase_admin.auth.verify_id_token", return_value=demo_token()):
        # Get eval-1
        evals_resp = client.get("/api/evaluations", headers={"Authorization": "Bearer demo"}).json()
        eval_1 = next(e for e in evals_resp["evaluations"] if e["status"] == "analysed")
        eval_1_id = eval_1["id"]

        results_resp = client.get(f"/api/evaluations/{eval_1_id}/results", headers={"Authorization": "Bearer demo"})
        assert results_resp.status_code == 200
        results = results_resp.json()

        # Find vendors by name
        bn_vendor = next(v for v in results["vendors"] if "BrightNest" in v["name"])
        shubh_vendor = next(v for v in results["vendors"] if "Shubh" in v["name"])
        uk_vendor = next(v for v in results["vendors"] if "UrbanKleen" in v["name"])

        # Check raw totals: 64.05 / 86.00 / 57.95
        assert bn_vendor["raw_score"] == 64.05, f"BrightNest raw score expected 64.05, got {bn_vendor['raw_score']}"
        assert shubh_vendor["raw_score"] == 86.0, f"Shubh raw score expected 86.00, got {shubh_vendor['raw_score']}"
        assert uk_vendor["raw_score"] == 57.95, f"UrbanKleen raw score expected 57.95, got {uk_vendor['raw_score']}"

        # Check display totals: 64 / 86 / 58
        assert bn_vendor["score"] == 64, f"BrightNest display score expected 64, got {bn_vendor['score']}"
        assert shubh_vendor["score"] == 86, f"Shubh display score expected 86, got {shubh_vendor['score']}"
        assert uk_vendor["score"] == 58, f"UrbanKleen display score expected 58, got {uk_vendor['score']}"

        # Check scoring matrix points for Mandatory compliance (weight 35)
        mand_row = next(r for r in results["scoring"] if r["criterion_key"] == "mandatory_compliance")
        bn_mand = mand_row["vendor_scores"][bn_vendor["id"]]
        shubh_mand = mand_row["vendor_scores"][shubh_vendor["id"]]
        uk_mand = mand_row["vendor_scores"][uk_vendor["id"]]

        # BrightNest: 83 * 35 / 100 = 29.05 -> display: 29.1
        assert bn_mand["raw_points"] == 29.05
        assert bn_mand["points"] == 29.1

        # Shubh: 100 * 35 / 100 = 35.00 -> display: 35.0
        assert shubh_mand["raw_points"] == 35.0
        assert shubh_mand["points"] == 35.0

        # UrbanKleen: 67 * 35 / 100 = 23.45 -> round half-up gives 23.5!
        assert uk_mand["raw_points"] == 23.45
        assert uk_mand["points"] == 23.5, f"UrbanKleen mandatory compliance half-up expected 23.5, got {uk_mand['points']}"


def test_changing_snapshot_weights_changes_totals_without_touching_stored_rows():
    with patch("firebase_admin.auth.verify_id_token", return_value=demo_token()):
        evals_resp = client.get("/api/evaluations", headers={"Authorization": "Bearer demo"}).json()
        eval_1 = next(e for e in evals_resp["evaluations"] if e["status"] == "analysed")
        eval_1_id = eval_1["id"]

        original_snap = []

        async def update_snapshot(weights_map=None, restore=False):
            nonlocal original_snap
            async with async_session() as s:
                from sqlalchemy import update
                e = await s.get(Evaluation, uuid.UUID(eval_1_id))
                if restore:
                    new_snap = original_snap
                else:
                    original_snap = [dict(item) for item in e.criteria_snapshot]
                    new_snap = [dict(item) for item in e.criteria_snapshot]
                    for item in new_snap:
                        if item["key"] in weights_map:
                            item["weight"] = weights_map[item["key"]]
                await s.execute(
                    update(Evaluation)
                    .where(Evaluation.id == uuid.UUID(eval_1_id))
                    .values(criteria_snapshot=new_snap)
                )
                await s.commit()

        try:
            # Modify only the snapshot weights on the evaluation (Mandatory: 50, Unresolved risks: 0)
            asyncio.run(update_snapshot({"mandatory_compliance": 50, "unresolved_risks": 0}))

            # Re-fetch results
            results_resp = client.get(f"/api/evaluations/{eval_1_id}/results", headers={"Authorization": "Bearer demo"})
            results = results_resp.json()

            bn_vendor = next(v for v in results["vendors"] if "BrightNest" in v["name"])
            # New BrightNest raw total with Mandatory at 50 (83*0.50=41.5) and Unresolved risks at 0:
            # 41.5 + 13.0 + 11.0 + 7.5 + 0 = 73.0
            assert bn_vendor["raw_score"] == 73.0
            assert bn_vendor["score"] == 73
        finally:
            asyncio.run(update_snapshot(restore=True))


def test_demo_seed_idempotent_security_and_pantry_requirements():
    async def run_seed_again():
        async with async_session() as s:
            await seed_demo_data(s)

    # Seed was already run once in fixture; run a second time to verify idempotency
    asyncio.run(run_seed_again())

    with patch("firebase_admin.auth.verify_id_token", return_value=demo_token()):
        auth = {"Authorization": "Bearer demo"}
        evals_resp = client.get("/api/evaluations", headers=auth).json()
        evals = {e["title"]: e for e in evals_resp["evaluations"]}

        sec_summary = evals["Security Services — Powai Campus"]
        pantry_summary = evals["Pantry & Cafeteria — BKC Office"]

        assert sec_summary["status"] == "requirements_review"
        assert sec_summary["total_requirements"] == 6
        assert sec_summary["mandatory_requirements"] == 4

        assert pantry_summary["status"] == "stale"
        assert pantry_summary["total_requirements"] == 5
        assert pantry_summary["mandatory_requirements"] == 3

        sec_reqs = client.get(f"/api/evaluations/{sec_summary['id']}/requirements", headers=auth).json()
        assert len(sec_reqs) == 6
        assert sum(1 for r in sec_reqs if r["mandatory"]) == 4
        assert [r["code"] for r in sec_reqs] == ["REQ-01", "REQ-02", "REQ-03", "REQ-04", "REQ-05", "REQ-06"]
        assert [r["position"] for r in sec_reqs] == [0, 1, 2, 3, 4, 5]
        for r in sec_reqs:
            assert r["origin"] == "extracted"
            assert r["source_document_id"] is None
            assert r["source_page"] is None
            assert r["source_section"] is None

        pantry_reqs = client.get(f"/api/evaluations/{pantry_summary['id']}/requirements", headers=auth).json()
        assert len(pantry_reqs) == 5
        assert sum(1 for r in pantry_reqs if r["mandatory"]) == 3
        assert [r["code"] for r in pantry_reqs] == ["REQ-01", "REQ-02", "REQ-03", "REQ-04", "REQ-05"]
        assert [r["position"] for r in pantry_reqs] == [0, 1, 2, 3, 4]
        for r in pantry_reqs:
            assert r["origin"] == "extracted"
            assert r["source_document_id"] is None
            assert r["source_page"] is None
            assert r["source_section"] is None

        # Ensure no fake documents were created on either evaluation
        sec_detail = client.get(f"/api/evaluations/{sec_summary['id']}", headers=auth).json()
        pantry_detail = client.get(f"/api/evaluations/{pantry_summary['id']}", headers=auth).json()
        assert sec_detail["documents"] == []
        assert pantry_detail["documents"] == []

