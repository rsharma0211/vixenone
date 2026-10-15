import asyncio
from decimal import Decimal
import io
import os
from pathlib import Path
from unittest.mock import patch
import uuid

import docx
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.database import async_session
from app.llm.client import (
    ExtractedCost,
    ExtractedCostItem,
    ExtractedCriterionFinding,
    ExtractedRequirementFinding,
    FakeGeminiClient,
    GeminiClientError,
    PageText,
    VendorAnalysisResult,
)
from app.main import app
from app.models.evaluation import (
    CostBreakdown,
    CriterionScore,
    Document,
    Evaluation,
    Finding,
)
from app.services.job_launcher import InlineJobLauncher, get_job_launcher
from app.services.scoring import (
    compute_cost_amounts,
    compute_cost_comparability_score,
    compute_judged_criterion_score,
    compute_mandatory_compliance_score,
    compute_recommendation,
    compute_unresolved_risks_score,
    deduplicate_clarifications,
)
from app.services.verification import (
    verify_quote_against_pages,
)
from tests.unit.test_documents_api import make_valid_pdf_bytes

client = TestClient(app)


def _fake_token(uid: str, email: str = "phase4_user@vixenone.app") -> dict:
    return {"uid": uid, "email": email, "name": "Phase4 User"}


def _make_pdf_bytes(page_count: int = 2) -> bytes:
    return make_valid_pdf_bytes(page_count=page_count)


def _make_docx_bytes() -> bytes:
    d = docx.Document()
    d.add_heading("1. Proposal Overview", level=1)
    d.add_paragraph("This is docx test content.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# =========================================================================
# 1. Quote verification unit tests
# =========================================================================

def test_quote_verification_normalisation_and_variants():
    pages = [
        PageText(
            page_number=1,
            text='We provide "premium" facilities—management with full-time supervisors.\nAll staff are trained.',
        ),
        PageText(
            page_number=2,
            text="Machinery is included as per schedule. Deep clean occurs quarterly.",
        ),
    ]

    # Exact match
    quote, page, needs_rev = verify_quote_against_pages(
        status="Compliant",
        quote='We provide "premium" facilities—management with full-time supervisors.',
        cited_page=1,
        pages=pages,
    )
    assert not needs_rev
    assert page == 1

    # Whitespace and linebreaks variant, curly quotes vs straight quotes, en-dash vs em-dash
    quote, page, needs_rev = verify_quote_against_pages(
        status="Compliant",
        quote="We provide “premium” facilities - management with   full-time\nsupervisors.",
        cited_page=1,
        pages=pages,
    )
    assert not needs_rev
    assert page == 1

    # Wrong page corrected
    quote, page, needs_rev = verify_quote_against_pages(
        status="Compliant",
        quote="Deep clean occurs quarterly.",
        cited_page=1,  # cited page 1, but actually on page 2
        pages=pages,
    )
    assert not needs_rev
    assert page == 2

    # Invented quote -> needs_review = True
    quote, page, needs_rev = verify_quote_against_pages(
        status="Compliant",
        quote="Invented hallucinated sentence nowhere in document.",
        cited_page=1,
        pages=pages,
    )
    assert needs_rev is True
    assert page == 1  # keeps cited page

    # Compliant with no quote -> needs_review = True
    quote, page, needs_rev = verify_quote_against_pages(
        status="Compliant",
        quote="",
        cited_page=1,
        pages=pages,
    )
    assert needs_rev is True

    # Partially compliant with no quote -> needs_review = True
    quote, page, needs_rev = verify_quote_against_pages(
        status="Partially compliant",
        quote=None,
        cited_page=1,
        pages=pages,
    )
    assert needs_rev is True

    # Not evidenced needs no quote -> needs_review = False
    quote, page, needs_rev = verify_quote_against_pages(
        status="Not evidenced",
        quote="",
        cited_page=None,
        pages=pages,
    )
    assert needs_rev is False


# =========================================================================
# 2. Costs arithmetic unit tests
# =========================================================================

def test_cost_arithmetic_exact_decimal_and_null_base():
    # 385000 -> 69300 / 454300
    res1 = compute_cost_amounts(Decimal("385000"), ["consumables"])
    assert res1["monthly_base"] == Decimal("385000")
    assert res1["gst_18"] == Decimal("69300.00")
    assert res1["monthly_total"] == Decimal("454300.00")
    assert res1["unknown"] == ["consumables"]

    # 460000 -> 82800 / 542800
    res2 = compute_cost_amounts(Decimal("460000"), [])
    assert res2["monthly_base"] == Decimal("460000")
    assert res2["gst_18"] == Decimal("82800.00")
    assert res2["monthly_total"] == Decimal("542800.00")

    # 410000 -> 73800 / 483800
    res3 = compute_cost_amounts(Decimal("410000"), [])
    assert res3["monthly_base"] == Decimal("410000")
    assert res3["gst_18"] == Decimal("73800.00")
    assert res3["monthly_total"] == Decimal("483800.00")

    # Null base -> gst and total null, and "Monthly base price not stated" appended to unknown
    res_null = compute_cost_amounts(None, ["extra bins"])
    assert res_null["monthly_base"] is None
    assert res_null["gst_18"] is None
    assert res_null["monthly_total"] is None
    assert "Monthly base price not stated" in res_null["unknown"]
    assert "extra bins" in res_null["unknown"]


# =========================================================================
# 3. Clarifications deduplication unit tests
# =========================================================================

def test_clarifications_deduplication():
    questions = [
        "Please clarify response SLA for emergencies.",
        "   please clarify response SLA for emergencies.  ",
        "What are the consumables charges?",
        "",
        "   ",
    ]
    deduped = deduplicate_clarifications(questions)
    assert len(deduped) == 2
    assert "Please clarify response SLA for emergencies." in deduped
    assert "What are the consumables charges?" in deduped


# =========================================================================
# 4. Scoring pure functions unit tests
# =========================================================================

def test_scoring_rules_and_floors():
    # Mandatory compliance: average over mandatory requirements
    # 2 mandatory: Compliant (100) and Partially compliant (50) -> 75
    s1 = compute_mandatory_compliance_score(["Compliant", "Partially compliant"])
    assert s1 == Decimal("75")

    # No mandatory requirements -> 100
    s_none = compute_mandatory_compliance_score([])
    assert s_none == Decimal("100")

    # Judged criterion
    assert compute_judged_criterion_score("Compliant") == Decimal("100")
    assert compute_judged_criterion_score("Partially compliant") == Decimal("50")
    assert compute_judged_criterion_score("Non-compliant") == Decimal("0")
    assert compute_judged_criterion_score("Not evidenced") == Decimal("0")
    assert compute_judged_criterion_score(None) == Decimal("0")

    # Cost comparability: 100 - 40 if base missing - 15 per unknown item; floor 0
    # base present, 2 unknowns -> 100 - 30 = 70
    assert compute_cost_comparability_score(Decimal("385000"), 2) == Decimal("70")
    # base missing, 1 unknown -> 100 - 40 - 15 = 45
    assert compute_cost_comparability_score(None, 1) == Decimal("45")
    # floor check: base missing, 5 unknowns -> 100 - 40 - 75 = -15 -> 0
    assert compute_cost_comparability_score(None, 5) == Decimal("0")

    # Unresolved risks: 100 - (high 20, medium 10, low 5) per finding/risk; floor 0
    items = [
        {"risk_types": ["Exclusion"], "severity": "High"},    # -20
        {"risk_types": ["Ambiguity"], "severity": "Medium"},  # -10
        {"risk_types": ["Omission"], "severity": "Low"},      # -5
        {"risk_types": [], "severity": "High"},               # no risk type -> not deducted
    ]
    # 100 - 35 = 65
    assert compute_unresolved_risks_score(items) == Decimal("65")

    # Floor check for unresolved risks
    many_high = [{"risk_types": ["Contradiction"], "severity": "High"} for _ in range(6)]
    assert compute_unresolved_risks_score(many_high) == Decimal("0")


def test_cost_comparability_scoring_rules():
    # 1. base null + 0 extracted unknowns -> 60
    assert compute_cost_comparability_score(None, 0) == Decimal("60")

    # 2. base null + 2 extracted unknowns -> 30
    assert compute_cost_comparability_score(None, 2) == Decimal("30")

    # 3. base present + 2 extracted unknowns -> 70
    assert compute_cost_comparability_score(Decimal("385000"), 2) == Decimal("70")

    # 4. base null + 5 extracted unknowns -> 0 (floor)
    assert compute_cost_comparability_score(None, 5) == Decimal("0")


# =========================================================================
# 5. Recommendation unit tests
# =========================================================================

def test_recommendation_rules():
    # Case 1: Clean recommendation
    vendors = [
        {
            "id": "v1",
            "name": "Vendor 1",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("85.50"),
        },
        {
            "id": "v2",
            "name": "Vendor 2",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("70.00"),
        },
    ]
    rec = compute_recommendation(vendors)
    assert rec["state"] == "recommended"
    assert rec["vendor_id"] == "v1"
    assert "Vendor 1: highest exact total (85.50)" in rec["reasons"][0]

    # Case 2: Mandatory failure excludes vendor
    vendors_fail = [
        {
            "id": "v1",
            "name": "Vendor 1",
            "eligible": False,  # mandatory failure
            "mandatory_failures": 1,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("90.00"),
        },
        {
            "id": "v2",
            "name": "Vendor 2",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("75.00"),
        },
    ]
    rec2 = compute_recommendation(vendors_fail)
    assert rec2["state"] == "recommended"
    assert rec2["vendor_id"] == "v2"

    # Case 3: Top vendor has mandatory not_evidenced -> insufficient
    vendors_not_ev = [
        {
            "id": "v1",
            "name": "BrightNest",
            "eligible": True,
            "mandatory_not_evidenced": 1,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("85.00"),
        },
        {
            "id": "v2",
            "name": "Vendor 2",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("70.00"),
        },
    ]
    rec3 = compute_recommendation(vendors_not_ev)
    assert rec3["state"] == "insufficient"
    assert rec3["vendor_id"] is None
    assert any("BrightNest: 1 mandatory requirement not evidenced" in r for r in rec3["reasons"])

    # Case 4: Top vendor has mandatory needs_review -> insufficient
    vendors_rev = [
        {
            "id": "v1",
            "name": "BrightNest",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 2,
            "exact_total": Decimal("85.00"),
        },
        {
            "id": "v2",
            "name": "Vendor 2",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("70.00"),
        },
    ]
    rec4 = compute_recommendation(vendors_rev)
    assert rec4["state"] == "insufficient"
    assert rec4["vendor_id"] is None
    assert any("BrightNest: 2 mandatory requirements need review" in r for r in rec4["reasons"])

    # Case 5: Tie on exact total -> insufficient
    vendors_tie = [
        {
            "id": "v1",
            "name": "Vendor 1",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("80.00"),
        },
        {
            "id": "v2",
            "name": "Vendor 2",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("80.00"),
        },
    ]
    rec5 = compute_recommendation(vendors_tie)
    assert rec5["state"] == "insufficient"
    assert rec5["vendor_id"] is None
    assert any("Tie on exact total" in r for r in rec5["reasons"])

    # Case 6: Fewer than 2 vendors -> insufficient
    vendors_one = [
        {
            "id": "v1",
            "name": "Vendor 1",
            "eligible": True,
            "mandatory_not_evidenced": 0,
            "mandatory_needs_review": 0,
            "exact_total": Decimal("80.00"),
        }
    ]
    rec6 = compute_recommendation(vendors_one)
    assert rec6["state"] == "insufficient"


# =========================================================================
# 6. API Integration tests: Preconditions, Snapshot, All-or-nothing, Weights
# =========================================================================

def _setup_eval_ready_for_analysis(uid: str):
    auth = {"Authorization": "Bearer token"}
    # Create evaluation with 2 vendors
    create_resp = client.post(
        "/api/evaluations",
        headers=auth,
        json={
            "title": "Andheri Housekeeping RFP",
            "category": "Housekeeping",
            "vendor_names": ["Vendor A", "Vendor B"],
        },
    )
    assert create_resp.status_code == 201
    eval_id = create_resp.json()["id"]
    vendor_ids = [v["id"] for v in create_resp.json()["vendors"]]

    # Upload requirements document
    req_pdf = _make_pdf_bytes(2)
    doc_resp = client.post(
        f"/api/evaluations/{eval_id}/documents",
        headers=auth,
        files={"file": ("rfp.pdf", req_pdf, "application/pdf")},
        data={"kind": "requirements"},
    )
    assert doc_resp.status_code == 200
    req_doc_id = doc_resp.json()["id"]

    # Upload proposal documents for each vendor
    v1_pdf = _make_pdf_bytes(2)
    p1_resp = client.post(
        f"/api/evaluations/{eval_id}/documents",
        headers=auth,
        files={"file": ("v1.pdf", v1_pdf, "application/pdf")},
        data={"kind": "proposal", "vendor_id": vendor_ids[0]},
    )
    assert p1_resp.status_code == 200
    p1_doc_id = p1_resp.json()["id"]

    v2_docx = _make_docx_bytes()
    p2_resp = client.post(
        f"/api/evaluations/{eval_id}/documents",
        headers=auth,
        files={"file": ("v2.docx", v2_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"kind": "proposal", "vendor_id": vendor_ids[1]},
    )
    assert p2_resp.status_code == 200
    p2_doc_id = p2_resp.json()["id"]

    # Add requirements directly
    reqs_payload = [
        {
            "code": "R1",
            "text": "Provide 10 cleaners",
            "category": "Manpower",
            "mandatory": True,
            "acceptance": "10 full-time cleaners",
            "source_document_id": req_doc_id,
            "source_page": 1,
            "source_section": "1.1",
        },
        {
            "code": "R2",
            "text": "Daily floor mopping",
            "category": "Operations",
            "mandatory": False,
            "acceptance": "Mopping done daily",
            "source_document_id": req_doc_id,
            "source_page": 1,
            "source_section": "1.2",
        },
    ]
    r_resp = client.put(f"/api/evaluations/{eval_id}/requirements", headers=auth, json=reqs_payload)
    assert r_resp.status_code == 200

    # Mark documents ready and evaluation status requirements_review directly in DB
    async def _mark_docs_ready():
        async with async_session() as s:
            for d_id in [req_doc_id, p1_doc_id, p2_doc_id]:
                d = await s.get(Document, uuid.UUID(d_id))
                if d:
                    d.status = "ready"
            ev = await s.get(Evaluation, uuid.UUID(eval_id))
            if ev:
                ev.status = "requirements_review"
            await s.commit()

    asyncio.run(_mark_docs_ready())
    return eval_id, vendor_ids, req_doc_id


def test_analyse_preconditions_422():
    uid = f"uid-p4-prec-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=_fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        # 1. Fewer than 2 vendors -> 422
        ev1 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Test 1 Vendor", "category": "Housekeeping", "vendor_names": ["V1"]},
        ).json()
        r1 = client.post(f"/api/evaluations/{ev1['id']}/analyse", headers=auth)
        assert r1.status_code == 422
        assert "Add at least 2 vendors" in r1.json()["detail"]

        # 2. Requirements doc missing / not ready -> 422
        ev2 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Test 2 Vendors", "category": "Housekeeping", "vendor_names": ["V1", "V2"]},
        ).json()
        r2 = client.post(f"/api/evaluations/{ev2['id']}/analyse", headers=auth)
        assert r2.status_code == 422
        assert "Requirements document is missing" in r2.json()["detail"]


def test_analyse_job_states_and_confirm_rerun():
    uid = f"uid-p4-rerun-{uuid.uuid4().hex}"
    fake_gemini = FakeGeminiClient(
        default_analysis=VendorAnalysisResult(
            requirement_findings=[
                ExtractedRequirementFinding(
                    code="R1",
                    status="compliant",
                    quote="Page 1 test content",
                    page=1,
                    section=None,
                    confidence="high",
                    is_inference=False,
                    risk_types=[],
                    severity="low",
                    clarification_question=None,
                )
            ],
            criterion_findings=[
                ExtractedCriterionFinding(
                    key="service_coverage",
                    status="compliant",
                    quote="Page 1 test content",
                    page=1,
                    section=None,
                    rationale="Covers all",
                )
            ],
            risks=[],
            cost=ExtractedCost(
                monthly_base=Decimal("385000"),
                included=[ExtractedCostItem(item="Cleaning")],
                excluded=[],
                optional=[],
                unknown=[],
            ),
        )
    )
    app.dependency_overrides[get_job_launcher] = lambda: InlineJobLauncher(
        async_session, lambda: fake_gemini
    )
    try:
        with patch("firebase_admin.auth.verify_id_token", return_value=_fake_token(uid)):
            auth = {"Authorization": "Bearer token"}
            eval_id, vendor_ids, req_doc_id = _setup_eval_ready_for_analysis(uid)

            # First run -> 202 Accepted, job completes to "done", evaluation status "analysed"
            resp = client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth)
            assert resp.status_code == 202
            assert resp.json()["status"] == "done"

            # Check status is analysed
            ev_detail = client.get(f"/api/evaluations/{eval_id}", headers=auth).json()
            assert ev_detail["status"] == "analysed"

            # Running again without confirm_rerun -> 409
            resp_409 = client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth)
            assert resp_409.status_code == 409
            assert "confirm_rerun=true" in resp_409.json()["detail"]

            # Running with confirm_rerun=True -> 202 Accepted
            resp_confirm = client.post(
                f"/api/evaluations/{eval_id}/analyse",
                headers=auth,
                json={"confirm_rerun": True},
            )
            assert resp_confirm.status_code == 202
            assert resp_confirm.json()["status"] == "done"
    finally:
        app.dependency_overrides.pop(get_job_launcher, None)


def test_analyse_all_or_nothing_atomic_transaction():
    uid = f"uid-p4-atomic-{uuid.uuid4().hex}"

    def _failing_vendor_handler(vendor_name: str) -> VendorAnalysisResult:
        if vendor_name == "Vendor B":
            raise GeminiClientError("Vendor B model failure")
        return VendorAnalysisResult(
            requirement_findings=[],
            criterion_findings=[],
            risks=[],
            cost=ExtractedCost(
                monthly_base=Decimal("385000"),
                included=[],
                excluded=[],
                optional=[],
                unknown=[],
            ),
        )

    fake_gemini = FakeGeminiClient(analysis_handler=_failing_vendor_handler)
    app.dependency_overrides[get_job_launcher] = lambda: InlineJobLauncher(
        async_session, lambda: fake_gemini
    )
    try:
        with patch("firebase_admin.auth.verify_id_token", return_value=_fake_token(uid)):
            auth = {"Authorization": "Bearer token"}
            eval_id, vendor_ids, req_doc_id = _setup_eval_ready_for_analysis(uid)

            resp = client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth)
            assert resp.status_code == 202
            assert resp.json()["status"] == "failed"

            # Verify nothing was written to database
            async def _check_db():
                async with async_session() as s:
                    f_stmt = select(Finding).where(Finding.evaluation_id == uuid.UUID(eval_id))
                    f_res = await s.execute(f_stmt)
                    assert len(list(f_res.scalars().all())) == 0

                    c_stmt = select(CostBreakdown).where(CostBreakdown.evaluation_id == uuid.UUID(eval_id))
                    c_res = await s.execute(c_stmt)
                    assert len(list(c_res.scalars().all())) == 0

    finally:
        app.dependency_overrides.pop(get_job_launcher, None)

        async def _cleanup():
            async with async_session() as s:
                from sqlalchemy import delete
                from app.models.evaluation import AnalysisJob, Evaluation
                await s.execute(delete(AnalysisJob).where(AnalysisJob.evaluation_id == uuid.UUID(eval_id)))
                await s.execute(delete(Evaluation).where(Evaluation.id == uuid.UUID(eval_id)))
                await s.commit()

        asyncio.run(_cleanup())


def test_weights_endpoint_and_user_criteria_untouched():
    uid = f"uid-p4-weights-{uuid.uuid4().hex}"
    fake_gemini = FakeGeminiClient(
        default_analysis=VendorAnalysisResult(
            requirement_findings=[],
            criterion_findings=[],
            risks=[],
            cost=ExtractedCost(
                monthly_base=Decimal("400000"),
                included=[],
                excluded=[],
                optional=[],
                unknown=[],
            ),
        )
    )
    app.dependency_overrides[get_job_launcher] = lambda: InlineJobLauncher(
        async_session, lambda: fake_gemini
    )
    try:
        with patch("firebase_admin.auth.verify_id_token", return_value=_fake_token(uid)):
            auth = {"Authorization": "Bearer token"}
            eval_id, vendor_ids, req_doc_id = _setup_eval_ready_for_analysis(uid)

            # Analyse to populate snapshot
            client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth)

            # Weights total != 100 -> 422
            bad_sum = client.put(
                f"/api/evaluations/{eval_id}/weights",
                headers=auth,
                json={
                    "mandatory_compliance": 50,
                    "service_coverage": 20,
                    "cost_comparability": 20,
                    "sla_operational": 10,
                    "unresolved_risks": 10,  # sum = 110
                },
            )
            assert bad_sum.status_code == 422
            assert "Weights must total exactly 100" in bad_sum.json()["detail"]

            # Wrong / missing keys -> 422
            bad_keys = client.put(
                f"/api/evaluations/{eval_id}/weights",
                headers=auth,
                json={"mandatory_compliance": 100},
            )
            assert bad_keys.status_code == 422
            assert "Weight keys must exactly match snapshot criteria keys" in bad_keys.json()["detail"]

            # Valid weights -> 200 and recomputes totals
            valid_resp = client.put(
                f"/api/evaluations/{eval_id}/weights",
                headers=auth,
                json={
                    "mandatory_compliance": 40,
                    "service_coverage": 20,
                    "cost_comparability": 20,
                    "sla_operational": 10,
                    "unresolved_risks": 10,
                },
            )
            assert valid_resp.status_code == 200
            snapshot = valid_resp.json()["criteria_snapshot"]
            mand_crit = next(c for c in snapshot if c["key"] == "mandatory_compliance")
            assert mand_crit["weight"] == 40

            # Verify user criteria was NOT modified
            user_crits = client.get("/api/criteria", headers=auth).json()
            user_mand = next(c for c in user_crits if c.get("builtin_key") == "mandatory_compliance")
            assert user_mand["weight"] == 35  # default untouched
    finally:
        app.dependency_overrides.pop(get_job_launcher, None)


def test_analyse_job_cost_comparability_e2e_no_double_penalty():
    uid = f"uid-p4-cost-e2e-{uuid.uuid4().hex}"
    fake_gemini = FakeGeminiClient(
        analysis_by_vendor={
            "Vendor A": VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="R1",
                        status="compliant",
                        quote="Page 1 test content",
                        page=1,
                        section=None,
                        confidence="high",
                        is_inference=False,
                        risk_types=[],
                        severity="low",
                        clarification_question=None,
                    )
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=None,
                    included=[],
                    excluded=[],
                    optional=[],
                    unknown=[],
                ),
            ),
            "Vendor B": VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="R1",
                        status="compliant",
                        quote="Page 1 test content",
                        page=1,
                        section=None,
                        confidence="high",
                        is_inference=False,
                        risk_types=[],
                        severity="low",
                        clarification_question=None,
                    )
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=Decimal("385000"),
                    included=[],
                    excluded=[],
                    optional=[],
                    unknown=[
                        ExtractedCostItem(item="Washroom consumables at actuals"),
                        ExtractedCostItem(item="Pest control on request"),
                    ],
                ),
            ),
        }
    )
    app.dependency_overrides[get_job_launcher] = lambda: InlineJobLauncher(
        async_session, lambda: fake_gemini
    )
    try:
        with patch("firebase_admin.auth.verify_id_token", return_value=_fake_token(uid)):
            auth = {"Authorization": "Bearer token"}
            eval_id, vendor_ids, req_doc_id = _setup_eval_ready_for_analysis(uid)

            # Trigger analysis job
            resp = client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth)
            assert resp.status_code == 202
            assert resp.json()["status"] == "done"

            # Query database directly for stored CriterionScore and CostBreakdown
            async def _verify_stored_cost_comparability():
                async with async_session() as s:
                    # Criterion scores for cost_comparability
                    scores_stmt = select(CriterionScore).where(
                        CriterionScore.evaluation_id == uuid.UUID(eval_id),
                        CriterionScore.criterion_key == "cost_comparability",
                    )
                    score_rows = (await s.execute(scores_stmt)).scalars().all()
                    scores_by_vendor = {str(cs.vendor_id): cs.score for cs in score_rows}

                    # Assert stored raw cost_comparability scores are 60 and 70
                    assert scores_by_vendor[vendor_ids[0]] == Decimal("60")
                    assert scores_by_vendor[vendor_ids[1]] == Decimal("70")

                    # Assert stored cost breakdown for Vendor A contains "Monthly base price not stated" in unknown
                    cb_stmt = select(CostBreakdown).where(
                        CostBreakdown.evaluation_id == uuid.UUID(eval_id),
                        CostBreakdown.vendor_id == uuid.UUID(vendor_ids[0]),
                    )
                    cb_v1 = (await s.execute(cb_stmt)).scalar_one()
                    assert cb_v1.monthly_base is None
                    assert "Monthly base price not stated" in cb_v1.unknown

            asyncio.run(_verify_stored_cost_comparability())
    finally:
        app.dependency_overrides.pop(get_job_launcher, None)


def test_cross_user_404_on_analyse_and_weights():
    uid1 = f"uid-p4-user1-{uuid.uuid4().hex}"
    uid2 = f"uid-p4-user2-{uuid.uuid4().hex}"
    auth1 = {"Authorization": "Bearer token1"}
    auth2 = {"Authorization": "Bearer token2"}

    with patch("firebase_admin.auth.verify_id_token", side_effect=lambda token: _fake_token(uid1) if token == "token1" else _fake_token(uid2)):
        # User 1 creates evaluation
        ev = client.post(
            "/api/evaluations",
            headers=auth1,
            json={"title": "User1 Eval", "category": "Housekeeping", "vendor_names": ["V1", "V2"]},
        ).json()
        eval_id = ev["id"]

        # User 2 tries to analyse -> 404
        r_analyse = client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth2)
        assert r_analyse.status_code == 404

        # User 2 tries to update weights -> 404
        r_weights = client.put(
            f"/api/evaluations/{eval_id}/weights",
            headers=auth2,
            json={"mandatory_compliance": 100},
        )
        assert r_weights.status_code == 404


@pytest.mark.skipif(
    not (os.getenv("RUN_GEMINI_LIVE") == "1"),
    reason="Live Gemini analysis smoke test skipped unless RUN_GEMINI_LIVE=1",
)
def test_live_gemini_smoke_full_pipeline():
    import time
    from app.llm.client import create_gemini_client

    dataset_dir = None
    candidates = [
        Path("/app/dataset"),
        Path(__file__).resolve().parents[2] / "dataset",
    ]
    for c in candidates:
        if c.exists():
            dataset_dir = c
            break
    assert dataset_dir is not None, "Dataset directory not found"

    uid = f"uid-p4-live-{uuid.uuid4().hex}"
    app.dependency_overrides[get_job_launcher] = lambda: InlineJobLauncher(
        async_session, create_gemini_client
    )
    try:
        with patch("firebase_admin.auth.verify_id_token", return_value=_fake_token(uid)):
            auth = {"Authorization": "Bearer token"}
            start_time = time.monotonic()

            # 1. Create evaluation
            r_ev = client.post(
                "/api/evaluations",
                headers=auth,
                json={
                    "title": "Live Smoke Housekeeping",
                    "category": "Housekeeping",
                    "vendor_names": [
                        "BrightNest Services",
                        "UrbanKleen Facility",
                        "Shubh Housekeeping",
                    ],
                },
            )
            assert r_ev.status_code == 201
            ev = r_ev.json()
            eval_id = ev["id"]
            vendor_map = {v["name"]: v["id"] for v in ev["vendors"]}

            # 2. Upload requirements PDF
            req_pdf = (dataset_dir / "requirements" / "01_Requirements_Andheri_Housekeeping.pdf").read_bytes()
            r_req = client.post(
                f"/api/evaluations/{eval_id}/documents",
                headers=auth,
                files={"file": ("requirements.pdf", req_pdf, "application/pdf")},
                data={"kind": "requirements"},
            )
            assert r_req.status_code == 200

            # 3. Upload vendor proposals
            bn_pdf = (dataset_dir / "proposals" / "02_BrightNest_Proposal.pdf").read_bytes()
            client.post(
                f"/api/evaluations/{eval_id}/documents",
                headers=auth,
                files={"file": ("brightnest.pdf", bn_pdf, "application/pdf")},
                data={"kind": "proposal", "vendor_id": vendor_map["BrightNest Services"]},
            )

            uk_pdf = (dataset_dir / "proposals" / "04_UrbanKleen_Proposal.pdf").read_bytes()
            client.post(
                f"/api/evaluations/{eval_id}/documents",
                headers=auth,
                files={"file": ("urbankleen.pdf", uk_pdf, "application/pdf")},
                data={"kind": "proposal", "vendor_id": vendor_map["UrbanKleen Facility"]},
            )

            shubh_docx = (dataset_dir / "proposals" / "03_Shubh_Proposal.docx").read_bytes()
            client.post(
                f"/api/evaluations/{eval_id}/documents",
                headers=auth,
                files={
                    "file": (
                        "shubh.docx",
                        shubh_docx,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                data={"kind": "proposal", "vendor_id": vendor_map["Shubh Housekeeping"]},
            )

            # 4. Run extraction
            r_ext = client.post(f"/api/evaluations/{eval_id}/extract", headers=auth)
            assert r_ext.status_code == 202
            assert r_ext.json()["status"] == "done"

            # 5. Run analysis
            r_ana = client.post(f"/api/evaluations/{eval_id}/analyse", headers=auth)
            assert r_ana.status_code == 202
            assert r_ana.json()["status"] == "done"

            elapsed = time.monotonic() - start_time

            # 6. Fetch results
            results_resp = client.get(f"/api/evaluations/{eval_id}/results", headers=auth)
            assert results_resp.status_code == 200
            results = results_resp.json()

            print("\n" + "=" * 60)
            print(f"LIVE SMOKE RESULTS (Wall-clock: {elapsed:.2f}s)")
            print("=" * 60)

            for v in results["vendors"]:
                print(f"\nVendor: {v['name']}")
                print(f"  Mandatory met / total: {v['mandatory_met']} / {v['mandatory_total']}")
                print(f"  Mandatory failures: {v['mandatory_failures']}")
                print(f"  Needs review count: {v['needs_review_count']}")
                print(f"  Base / GST / Total: {v['monthly_base_inr']} / {v['monthly_gst_inr']} / {v['monthly_total_inr']}")
                print(f"  Criterion scores: {v['criterion_scores']}")
                print(f"  Exact total: {v['exact_total']} (display: {v['score']})")

            rec = results["recommendation"]
            print(f"\nRecommendation state: {rec['state']}, vendor_id: {rec['vendor_id']}")
            print(f"Reasons: {rec['reasons']}")

            # Verify planted issues in findings and costs
            all_findings = results.get("findings", [])
            all_costs = results.get("costs", [])
            findings_text = " ".join(
                (f.get("evidence_quote") or "") + " " + (f.get("clarification_question") or "") + " " + " ".join(f.get("risk_types") or [])
                for f in all_findings
            ).lower()
            costs_text = " ".join(
                " ".join(c.get("included", []) + c.get("excluded", []) + c.get("optional", []) + c.get("unknown", []))
                for c in all_costs
            ).lower()
            combined_text = findings_text + " " + costs_text

            planted_issues_found = {
                "BrightNest: consumables at actuals": ("actuals" in combined_text or "consumables" in combined_text),
                "BrightNest: pest control as applicable": ("as applicable" in combined_text or "pest" in combined_text),
                "BrightNest: deep clean excluded": ("deep" in combined_text or "clean" in combined_text),
                "UrbanKleen: adequate manpower": ("adequate" in combined_text or "manpower" in combined_text),
                "UrbanKleen: day-only supervisor": ("day" in combined_text or "supervisor" in combined_text),
                "UrbanKleen: reasonable usage": ("reasonable" in combined_text or "usage" in combined_text),
                "UrbanKleen: Mon-Sat schedule": ("mon" in combined_text or "saturday" in combined_text or "sat" in combined_text),
            }
            print("\nPlanted issues detected:")
            for issue, found in planted_issues_found.items():
                print(f"  - {issue}: {'YES' if found else 'NO'}")

            # Check Shubh is top vendor or eligible
            sorted_vendors = sorted(results["vendors"], key=lambda x: Decimal(str(x["exact_total"] or 0)), reverse=True)
            top_vendor = sorted_vendors[0]
            print(f"\nTop vendor by exact score: {top_vendor['name']} ({top_vendor['exact_total']})")
            assert "Shubh" in top_vendor["name"], f"Expected Shubh to be top vendor, got {top_vendor['name']}"
            print("=" * 60 + "\n")
    finally:
        app.dependency_overrides.pop(get_job_launcher, None)

