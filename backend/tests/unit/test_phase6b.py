import io
from pathlib import Path
from typing import Any, Dict, List
import uuid

import pdfplumber
import pytest
from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.database import async_session
from app.llm.client import (
    ExtractedCost,
    ExtractedCostItem,
    ExtractedRequirement,
    ExtractedRequirementFinding,
    FakeGeminiClient,
    LLMComplianceStatus,
    LLMConfidence,
    PageText,
    VendorAnalysisResult,
)
from app.models.evaluation import (
    AnalysisJob,
    Document,
    DocumentPage,
    Evaluation,
    Finding,
    Requirement,
    Vendor,
)
from app.models.user import User
from app.services.seed import run_seed
from app.services.seed_demo import DEMO_EMAIL
from app.services.storage import LocalStorageService
from app.services.worker import (
    STORAGE_FILE_MISSING_ERROR,
    STORAGE_READ_FAILURE_ERROR,
    run_job_by_id,
)
from tests.unit.test_seed import FakeAuthAdmin

EVAL_1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
EVAL_2_ID = uuid.UUID("11111111-2222-1111-1111-111111111111")
EVAL_3_ID = uuid.UUID("11111111-3333-1111-1111-111111111111")
EVAL_4_ID = uuid.UUID("11111111-4444-1111-1111-111111111111")


def _build_content_based_fake_gemini(dataset_dir: Path) -> FakeGeminiClient:
    """Create a FakeGeminiClient that makes decisions based on content, not call order."""
    def pdf_handler(pdf_bytes: bytes) -> List[PageText]:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return [
                PageText(page_number=idx, text=p.extract_text() or "")
                for idx, p in enumerate(pdf.pages, start=1)
            ]

    def requirements_handler(pages: List[PageText]) -> List[ExtractedRequirement]:
        full_text = " ".join(p.text for p in pages).lower()
        if "housekeeping" in full_text or "andheri" in full_text:
            return [
                ExtractedRequirement(
                    code="REQ-01",
                    text="Daily cleaning of all office areas, Monday to Saturday, 07:00–19:00.",
                    category="Service",
                    mandatory=True,
                    acceptance="Schedule stated in proposal",
                    source_page=1,
                    source_section="§2.0",
                ),
                ExtractedRequirement(
                    code="REQ-02",
                    text="Minimum 12 housekeeping staff per shift, two shifts per day.",
                    category="Staffing",
                    mandatory=True,
                    acceptance="Headcount per shift stated",
                    source_page=1,
                    source_section="§2.0",
                ),
            ]
        elif "pest" in full_text or "termite" in full_text or "thane" in full_text:
            return [
                ExtractedRequirement(
                    code="REQ-01",
                    text="Monthly general pest control of the whole warehouse (mandatory).",
                    category="Service",
                    mandatory=True,
                    acceptance="General pest management carried out monthly across the entire warehouse.",
                    source_page=1,
                    source_section="1. Scope of Pest Mitigation Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-02",
                    text="Rodent bait stations on the perimeter, checked fortnightly (mandatory).",
                    category="Service",
                    mandatory=True,
                    acceptance="Perimeter bait stations inspected and serviced on a fortnightly cadence.",
                    source_page=1,
                    source_section="1. Scope of Pest Mitigation Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-03",
                    text="Annual termite treatment (mandatory).",
                    category="Service",
                    mandatory=True,
                    acceptance="Complete termite preventive/curative treatment conducted annually.",
                    source_page=1,
                    source_section="1. Scope of Pest Mitigation Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-04",
                    text="Only government-approved chemicals; safety data sheets shared (mandatory).",
                    category="Compliance",
                    mandatory=True,
                    acceptance="Certified chemicals used exclusively; manufacturer safety data sheets provided.",
                    source_page=1,
                    source_section="1. Scope of Pest Mitigation Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-05",
                    text="Service report after each visit.",
                    category="Operations",
                    mandatory=False,
                    acceptance="Service activity report submitted immediately after every service visit.",
                    source_page=1,
                    source_section="1. Scope of Pest Mitigation Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-06",
                    text="Emergency call-out within 24 hours.",
                    category="Operations",
                    mandatory=False,
                    acceptance="Response and site visit provided within 24 hours of an emergency notice.",
                    source_page=1,
                    source_section="1. Scope of Pest Mitigation Requirements",
                ),
            ]
        elif "security" in full_text or "powai" in full_text:
            return [
                ExtractedRequirement(
                    code="REQ-01",
                    text="Trained guards 24×7 at all three campus gates (mandatory).",
                    category="Service",
                    mandatory=True,
                    acceptance="24x7 coverage at all gates",
                    source_page=1,
                    source_section="1. Scope of Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-02",
                    text="Valid private security agency licence for Maharashtra (mandatory).",
                    category="Compliance",
                    mandatory=True,
                    acceptance="Licence copy submitted",
                    source_page=1,
                    source_section="1. Scope of Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-03",
                    text="One security supervisor on site every shift (mandatory).",
                    category="Staffing",
                    mandatory=True,
                    acceptance="Supervisor on duty each shift",
                    source_page=1,
                    source_section="1. Scope of Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-04",
                    text="Visitor log at reception for every entry and exit (mandatory).",
                    category="Operations",
                    mandatory=True,
                    acceptance="Visitor log maintained",
                    source_page=1,
                    source_section="1. Scope of Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-05",
                    text="Fire-safety training within 30 days of deployment.",
                    category="Training",
                    mandatory=False,
                    acceptance="Training certificates provided",
                    source_page=1,
                    source_section="1. Scope of Requirements",
                ),
                ExtractedRequirement(
                    code="REQ-06",
                    text="Monthly incident report to the facilities manager.",
                    category="Reporting",
                    mandatory=False,
                    acceptance="Incident reports sent monthly",
                    source_page=1,
                    source_section="1. Scope of Requirements",
                ),
            ]
        elif "pantry" in full_text or "cafeteria" in full_text or "fssai" in full_text or "bkc" in full_text:
            return [
                ExtractedRequirement(
                    code="REQ-01",
                    text="Valid FSSAI licence (mandatory).",
                    category="Compliance",
                    mandatory=True,
                    acceptance="FSSAI certificate provided",
                    source_page=1,
                    source_section="1. Requirements Specifications",
                ),
                ExtractedRequirement(
                    code="REQ-02",
                    text="Breakfast and lunch Monday to Friday for up to 150 staff (mandatory).",
                    category="Service",
                    mandatory=True,
                    acceptance="Meals delivered as scheduled",
                    source_page=1,
                    source_section="1. Requirements Specifications",
                ),
                ExtractedRequirement(
                    code="REQ-03",
                    text="Daily kitchen hygiene checklist signed by the supervisor (mandatory).",
                    category="Compliance",
                    mandatory=True,
                    acceptance="Checklist signed daily",
                    source_page=1,
                    source_section="1. Requirements Specifications",
                ),
                ExtractedRequirement(
                    code="REQ-04",
                    text="Weekly menu shared every Friday.",
                    category="Operations",
                    mandatory=False,
                    acceptance="Menu published on time",
                    source_page=1,
                    source_section="1. Requirements Specifications",
                ),
                ExtractedRequirement(
                    code="REQ-05",
                    text="Tea and coffee stations refilled twice daily.",
                    category="Service",
                    mandatory=False,
                    acceptance="Refills done twice daily",
                    source_page=1,
                    source_section="1. Requirements Specifications",
                ),
            ]
        else:
            return [
                ExtractedRequirement(
                    code="REQ-01",
                    text="Daily cleaning of all office areas, Monday to Saturday, 07:00–19:00.",
                    category="Service",
                    mandatory=True,
                    acceptance="Schedule stated in proposal",
                    source_page=1,
                    source_section="§2.0",
                ),
                ExtractedRequirement(
                    code="REQ-02",
                    text="Minimum 12 housekeeping staff per shift, two shifts per day.",
                    category="Staffing",
                    mandatory=True,
                    acceptance="Headcount per shift stated",
                    source_page=1,
                    source_section="§2.0",
                ),
            ]

    def analysis_handler(
        vendor_name: str,
        requirements: List[Dict[str, Any]],
        judged_criteria: List[Dict[str, Any]],
        pages: List[PageText],
    ) -> VendorAnalysisResult:
        full_page_text = " ".join(p.text for p in pages)
        assert len(full_page_text) > 0
        v_lower = vendor_name.lower()

        if "secureshield" in v_lower:
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="deploying trained guards 24×7 at all three campus gates",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="valid private security agency licence for Maharashtra under registration number PSARA-MH-2023-F9876, valid to 2028",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-03",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="One dedicated security supervisor is stationed on site every shift",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-04",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="formal visitor register at reception is strictly maintained for every entry and exit",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-05",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="certified fire-safety training within 30 days of initial deployment",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-06",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="detailed monthly incident report will be submitted directly to the facilities manager",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=320000,
                    included=[ExtractedCostItem(item="Guard deployments"), ExtractedCostItem(item="On-site supervision")],
                    excluded=[],
                    optional=[],
                    unknown=[],
                ),
            )
        elif "apex" in v_lower:
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="Gates 1–2 manned 24×7, while Gate 3 will have day shift only coverage",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="private security agency licence renewal applied for with the controlling authority",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-03",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="supervisor night shift on request",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-04",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="visitor log maintained at reception for tracking building entries and exits",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-05",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="fire-safety training is available on request, at additional cost",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-06",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="quarterly incident report to client management",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=265000,
                    included=[ExtractedCostItem(item="Base security services fee")],
                    excluded=[],
                    optional=[ExtractedCostItem(item="Fire-safety training")],
                    unknown=[ExtractedCostItem(item="Overtime")],
                ),
            )
        elif "freshbite" in v_lower:
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="FreshBite Caterers holds an active food safety licence with FSSAI licence number stated: FSSAI-MH-2023-009876543210.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="providing breakfast and lunch Monday to Friday for up to 150 staff members daily.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-03",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="daily kitchen hygiene checklist signed by the supervisor",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-04",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="weekly menu shared every Friday",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-05",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="tea and coffee stations refilled twice daily",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=210000,
                    included=[ExtractedCostItem(item="Base cafeteria service fee"), ExtractedCostItem(item="All culinary raw materials")],
                    excluded=[],
                    optional=[],
                    unknown=[],
                ),
            )
        elif "gourmet" in v_lower:
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.NON_COMPLIANT,
                        quote="FSSAI registration in process",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="breakfast and lunch Monday to Saturday for up to 120 staff",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-03",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="weekly hygiene checklist",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-04",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="menu shared monthly",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-05",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="tea and coffee stations refilled once daily",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=185000,
                    included=[ExtractedCostItem(item="Base fee")],
                    excluded=[],
                    optional=[],
                    unknown=[ExtractedCostItem(item="Plates beyond 120 staff"), ExtractedCostItem(item="Extra tea/coffee refills")],
                ),
            )
        elif "brightnest" in v_lower:
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="Daily cleaning of all office areas, Monday to Saturday, 07:00 to 19:00.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="12 housekeeping staff per shift across two shifts.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=385000,
                    included=[ExtractedCostItem(item="Staffing")],
                    excluded=[ExtractedCostItem(item="Consumables")],
                    optional=[],
                    unknown=[],
                ),
            )
        elif "shubh" in v_lower:
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="Daily cleaning of all office areas, Monday to Saturday, 07:00 to 19:00.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="14 housekeeping staff per shift across two shifts.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=460000,
                    included=[ExtractedCostItem(item="Staffing"), ExtractedCostItem(item="Pest control")],
                    excluded=[],
                    optional=[],
                    unknown=[],
                ),
            )
        else:  # UrbanKleen
            return VendorAnalysisResult(
                requirement_findings=[
                    ExtractedRequirementFinding(
                        code="REQ-01",
                        status=LLMComplianceStatus.COMPLIANT,
                        quote="Daily cleaning of office areas, Monday to Saturday, 07:00 to 19:00.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                    ExtractedRequirementFinding(
                        code="REQ-02",
                        status=LLMComplianceStatus.PARTIALLY_COMPLIANT,
                        quote="Adequate manpower as required will be deployed to maintain cleanliness standards.",
                        page=1,
                        confidence=LLMConfidence.HIGH,
                    ),
                ],
                criterion_findings=[],
                risks=[],
                cost=ExtractedCost(
                    monthly_base=410000,
                    included=[ExtractedCostItem(item="Staffing")],
                    excluded=[],
                    optional=[],
                    unknown=[],
                ),
            )

    return FakeGeminiClient(
        pdf_handler=pdf_handler,
        requirements_handler=requirements_handler,
        analysis_handler=analysis_handler,
    )


@pytest.mark.asyncio
async def test_seed_on_empty_db_succeeds_and_uploads_4_files(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        # Clear existing demo user and evals to test on empty state
        await session.execute(delete(Evaluation).execution_options(synchronize_session=False))
        await session.execute(delete(User).where(User.email == DEMO_EMAIL).execution_options(synchronize_session=False))
        await session.commit()

        # Seed on empty database
        user = await run_seed(session=session, auth_admin=fake_admin, storage=storage)
        assert user is not None

        # Verify 4 documents created in DB
        docs = list((await session.execute(
            select(Document).where(Document.evaluation_id == EVAL_1_ID).order_by(Document.filename)
        )).scalars().all())
        assert len(docs) == 4

        expected_filenames = [
            "BrightNest_Proposal.pdf",
            "RFP_Housekeeping_Andheri.pdf",
            "Shubh_Proposal.docx",
            "UrbanKleen_Proposal.pdf",
        ]
        assert [d.filename for d in docs] == expected_filenames

        # Verify files exist in storage at the exact seeded keys and have real size/page counts
        for d in docs:
            assert await storage.exists(d.storage_key) is True
            file_bytes = await storage.read(d.storage_key)
            assert len(file_bytes) == d.size_bytes
            assert d.size_bytes > 0
            assert d.page_count is not None and d.page_count >= 1

            # Verify DocumentPage rows were seeded for every document
            pages = list((await session.execute(
                select(DocumentPage).where(DocumentPage.document_id == d.id).order_by(DocumentPage.page_number)
            )).scalars().all())
            assert len(pages) == d.page_count
            for p in pages:
                assert len(p.text.strip()) > 0


@pytest.mark.asyncio
async def test_seed_twice_same_rows_same_files_no_duplicates(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        # First run
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        eval_count_1 = (await session.execute(select(func.count(Evaluation.id)))).scalar_one()
        doc_count_1 = (await session.execute(select(func.count(Document.id)))).scalar_one()
        page_count_1 = (await session.execute(select(func.count(DocumentPage.id)))).scalar_one()
        vendor_count_1 = (await session.execute(select(func.count(Vendor.id)))).scalar_one()
        req_count_1 = (await session.execute(select(func.count(Requirement.id)))).scalar_one()

        # Second run
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        eval_count_2 = (await session.execute(select(func.count(Evaluation.id)))).scalar_one()
        doc_count_2 = (await session.execute(select(func.count(Document.id)))).scalar_one()
        page_count_2 = (await session.execute(select(func.count(DocumentPage.id)))).scalar_one()
        vendor_count_2 = (await session.execute(select(func.count(Vendor.id)))).scalar_one()
        req_count_2 = (await session.execute(select(func.count(Requirement.id)))).scalar_one()

        assert eval_count_2 == eval_count_1
        assert doc_count_2 == doc_count_1
        assert page_count_2 == page_count_1
        assert vendor_count_2 == vendor_count_1
        assert req_count_2 == req_count_1

        # Check storage keys: exactly 4 files
        docs = (await session.execute(select(Document).where(Document.evaluation_id == EVAL_1_ID))).scalars().all()
        assert len(docs) == 4
        for d in docs:
            assert await storage.exists(d.storage_key) is True


@pytest.mark.asyncio
async def test_extraction_job_on_seeded_evaluation_completes(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # Create extraction job for seeded evaluation 1
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_1_ID,
            kind="extract_requirements",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    # Run extraction job
    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: storage,
    )

    async with async_session() as session:
        updated_job = await session.get(AnalysisJob, job_id)
        assert updated_job is not None
        assert updated_job.status == "done"
        assert updated_job.error_message is None

        eval_obj = await session.get(Evaluation, EVAL_1_ID)
        assert eval_obj is not None
        assert eval_obj.status == "requirements_review"

        reqs = list((await session.execute(
            select(Requirement).where(Requirement.evaluation_id == EVAL_1_ID)
        )).scalars().all())
        assert len(reqs) == 2


@pytest.mark.asyncio
async def test_analysis_job_on_seeded_evaluation_completes(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # Create analysis job for seeded evaluation 1
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_1_ID,
            kind="analyse",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    # Run analysis job
    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: storage,
    )

    async with async_session() as session:
        updated_job = await session.get(AnalysisJob, job_id)
        assert updated_job is not None
        assert updated_job.status == "done"
        assert updated_job.error_message is None

        eval_obj = await session.get(Evaluation, EVAL_1_ID)
        assert eval_obj is not None
        assert eval_obj.status == "analysed"

        findings = list((await session.execute(
            select(Finding).where(Finding.evaluation_id == EVAL_1_ID)
        )).scalars().all())
        assert len(findings) > 0


@pytest.mark.asyncio
async def test_missing_file_error_equals_exact_friendly_text(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # Intentionally delete the requirements file from storage
        docs = list((await session.execute(
            select(Document).where(Document.evaluation_id == EVAL_1_ID)
        )).scalars().all())
        target_doc = next(d for d in docs if d.kind == "requirements")
        await storage.delete(target_doc.storage_key)
        assert await storage.exists(target_doc.storage_key) is False

        # Create extraction job
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_1_ID,
            kind="extract_requirements",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id
        target_doc_id = target_doc.id

    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    # Run extraction job
    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: storage,
    )

    async with async_session() as session:
        failed_job = await session.get(AnalysisJob, job_id)
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert failed_job.error_message == STORAGE_FILE_MISSING_ERROR
        assert failed_job.error_message == "This file is missing. Please upload it again."

        failed_doc = await session.get(Document, target_doc_id)
        assert failed_doc is not None
        assert failed_doc.status == "error"
        assert failed_doc.error_message == STORAGE_FILE_MISSING_ERROR
        assert failed_doc.error_message == "This file is missing. Please upload it again."

        # Verify no error message contains 'evaluations/' or a file path
        assert "evaluations/" not in failed_job.error_message
        assert "evaluations/" not in failed_doc.error_message
        assert "/" not in failed_job.error_message and "\\" not in failed_job.error_message
        assert "/" not in failed_doc.error_message and "\\" not in failed_doc.error_message


@pytest.mark.asyncio
async def test_storage_read_failure_error_equals_exact_friendly_text(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        docs = list((await session.execute(
            select(Document).where(Document.evaluation_id == EVAL_1_ID)
        )).scalars().all())
        target_doc = next(d for d in docs if d.kind == "requirements")
        target_doc_id = target_doc.id

        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_1_ID,
            kind="extract_requirements",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    # Create a wrapper storage where read raises an unexpected I/O error
    class FailingStorage(LocalStorageService):
        async def read(self, path: str) -> bytes:
            raise OSError("Hardware drive error at /dev/sda1")

    failing_storage = FailingStorage(base_dir=str(tmp_path / "uploads"))
    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: failing_storage,
    )

    async with async_session() as session:
        failed_job = await session.get(AnalysisJob, job_id)
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert failed_job.error_message == STORAGE_READ_FAILURE_ERROR
        assert failed_job.error_message == "This file could not be read. Please upload it again."

        failed_doc = await session.get(Document, target_doc_id)
        assert failed_doc is not None
        assert failed_doc.status == "error"
        assert failed_doc.error_message == STORAGE_READ_FAILURE_ERROR
        assert failed_doc.error_message == "This file could not be read. Please upload it again."

        # Verify no error message contains internal paths or exception details
        assert "evaluations/" not in failed_job.error_message
        assert "evaluations/" not in failed_doc.error_message
        assert "/" not in failed_job.error_message and "\\" not in failed_job.error_message
        assert "/" not in failed_doc.error_message and "\\" not in failed_doc.error_message
        assert "Hardware" not in failed_job.error_message
        assert "sda1" not in failed_job.error_message


@pytest.mark.asyncio
async def test_powai_ready_and_analysis_job_completes(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # 1. Powai: 3 documents ready
        docs = list((await session.execute(
            select(Document).where(Document.evaluation_id == EVAL_2_ID).order_by(Document.filename)
        )).scalars().all())
        assert len(docs) == 3
        for d in docs:
            assert d.status == "ready"
            assert d.page_count is not None and d.page_count >= 1

        # 2. 6 requirements / 4 mandatory with source pages
        reqs = list((await session.execute(
            select(Requirement).where(Requirement.evaluation_id == EVAL_2_ID).order_by(Requirement.position)
        )).scalars().all())
        assert len(reqs) == 6
        assert sum(1 for r in reqs if r.mandatory) == 4
        for r in reqs:
            assert r.source_page is not None and r.source_page == 1
            assert r.source_document_id is not None

        # Create analysis job for Powai
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_2_ID,
            kind="analyse",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    # Run analysis job
    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: storage,
    )

    async with async_session() as session:
        updated_job = await session.get(AnalysisJob, job_id)
        assert updated_job is not None
        assert updated_job.status == "done"
        assert updated_job.error_message is None

        powai_eval = await session.get(Evaluation, EVAL_2_ID)
        assert powai_eval is not None
        assert powai_eval.status == "analysed"

        findings = list((await session.execute(
            select(Finding).where(Finding.evaluation_id == EVAL_2_ID)
        )).scalars().all())
        assert len(findings) > 0


@pytest.mark.asyncio
async def test_pantry_stale_and_reanalysis_job_completes(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # 1. Pantry: stale, results present
        pantry_eval = await session.get(Evaluation, EVAL_3_ID)
        assert pantry_eval is not None
        assert pantry_eval.status == "stale"

        # 2. REQ-02 reads 175
        reqs = list((await session.execute(
            select(Requirement).where(Requirement.evaluation_id == EVAL_3_ID).order_by(Requirement.position)
        )).scalars().all())
        assert len(reqs) == 5
        req_02 = next(r for r in reqs if r.code == "REQ-02")
        assert "175 staff" in req_02.text
        assert req_02.origin == "user"

        initial_findings = list((await session.execute(
            select(Finding).where(Finding.evaluation_id == EVAL_3_ID)
        )).scalars().all())
        assert len(initial_findings) > 0

        # Create re-analysis job for Pantry
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_3_ID,
            kind="analyse",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    # Run re-analysis job
    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: storage,
    )

    async with async_session() as session:
        updated_job = await session.get(AnalysisJob, job_id)
        assert updated_job is not None
        assert updated_job.status == "done"
        assert updated_job.error_message is None

        updated_eval = await session.get(Evaluation, EVAL_3_ID)
        assert updated_eval is not None
        assert updated_eval.status == "analysed"


@pytest.mark.asyncio
async def test_thane_uploaded_and_extraction_job_completes(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # 1. Thane: 3 documents uploaded (not read), 0 requirements, status draft
        docs = list((await session.execute(
            select(Document).where(Document.evaluation_id == EVAL_4_ID).order_by(Document.filename)
        )).scalars().all())
        assert len(docs) == 3
        for d in docs:
            assert d.status == "uploaded"

        reqs = list((await session.execute(
            select(Requirement).where(Requirement.evaluation_id == EVAL_4_ID)
        )).scalars().all())
        assert len(reqs) == 0

        thane_eval = await session.get(Evaluation, EVAL_4_ID)
        assert thane_eval is not None
        assert thane_eval.status == "draft"

        # Create extraction job for Thane
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=EVAL_4_ID,
            kind="extract_requirements",
            status="queued",
            step_label="Queued",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    fake_client = _build_content_based_fake_gemini(settings.dataset_path)

    # Run extraction job
    await run_job_by_id(
        job_id=job_id,
        session_factory=async_session,
        gemini_client_factory=lambda: fake_client,
        storage_factory=lambda: storage,
    )

    async with async_session() as session:
        updated_job = await session.get(AnalysisJob, job_id)
        assert updated_job is not None
        assert updated_job.status == "done"
        assert updated_job.error_message is None

        updated_eval = await session.get(Evaluation, EVAL_4_ID)
        assert updated_eval is not None
        assert updated_eval.status == "requirements_review"

        extracted_reqs = list((await session.execute(
            select(Requirement).where(Requirement.evaluation_id == EVAL_4_ID).order_by(Requirement.position)
        )).scalars().all())
        assert len(extracted_reqs) == 6
        assert sum(1 for r in extracted_reqs if r.mandatory) == 4


@pytest.mark.asyncio
async def test_andheri_totals_and_locations_unchanged(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        user = await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        # 1. Andheri totals still 64 / 86 / 58
        from app.models.company import Location
        from app.services.evaluation_service import EvaluationService

        results = await EvaluationService.get_results(session, user.id, EVAL_1_ID)
        vendor_totals = {v.name: v.score for v in results.vendors}
        assert vendor_totals["BrightNest Facility Services"] == 64
        assert vendor_totals["Shubh Housekeeping Pvt Ltd"] == 86
        assert vendor_totals["UrbanKleen Services"] == 58

        raw_totals = {v.name: v.raw_score for v in results.vendors}
        assert raw_totals["BrightNest Facility Services"] == 64.05
        assert raw_totals["Shubh Housekeeping Pvt Ltd"] == 86.0
        assert raw_totals["UrbanKleen Services"] == 57.95

        # 2. Location links unchanged (4 demo locations exist for the company)
        locs = list((await session.execute(select(Location).where(Location.company_id == user.company_id))).scalars().all())
        assert len(locs) == 4
        loc_names = {loc.name for loc in locs}
        assert loc_names == {
            "Andheri East Office",
            "Powai Campus",
            "BKC Office",
            "Thane Warehouse",
        }


@pytest.mark.asyncio
async def test_no_seeded_job_is_running_or_failed(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        await run_seed(session=session, auth_admin=fake_admin, storage=storage)

        bad_jobs = list((await session.execute(
            select(AnalysisJob).where(AnalysisJob.status.in_(["extracting", "analysing", "failed", "running"]))
        )).scalars().all())
        assert len(bad_jobs) == 0


def test_production_image_excludes_generator_and_includes_test_packs():
    # 1. Verify .dockerignore contains dev/
    dockerignore_path = Path("/app/.dockerignore") if Path("/app/.dockerignore").exists() else Path("backend/.dockerignore")
    if not dockerignore_path.exists():
        dockerignore_path = Path(__file__).parent.parent.parent / ".dockerignore"
    assert dockerignore_path.exists()
    dockerignore_text = dockerignore_path.read_text(encoding="utf-8")
    assert "dev/" in dockerignore_text or "dev" in dockerignore_text

    # 2. Verify dev document generator exists in dev directory
    dev_gen_path = Path("/app/dev/generate_documents.py") if Path("/app/dev/generate_documents.py").exists() else Path("backend/dev/generate_documents.py")
    if not dev_gen_path.exists():
        dev_gen_path = Path(__file__).parent.parent.parent / "dev" / "generate_documents.py"
    assert dev_gen_path.exists()

    # 3. Verify all 13 test pack files are present in dataset
    dataset_dir = settings.dataset_path
    req_files = [
        "requirements/01_Requirements_Andheri_Housekeeping.pdf",
        "requirements/05_Requirements_Powai_Security.pdf",
        "requirements/08_Requirements_Pantry_BKC.pdf",
        "requirements/11_Requirements_Thane_PestControl.pdf",
    ]
    prop_files = [
        "proposals/02_BrightNest_Proposal.pdf",
        "proposals/03_Shubh_Proposal.docx",
        "proposals/04_UrbanKleen_Proposal.pdf",
        "proposals/06_SecureShield_Proposal.pdf",
        "proposals/07_Apex_Proposal.docx",
        "proposals/09_FreshBite_Proposal.docx",
        "proposals/10_Gourmet_Proposal.pdf",
        "proposals/12_TermiGuard_Proposal.pdf",
        "proposals/13_SafeClean_Proposal.docx",
    ]
    for rf in req_files + prop_files:
        p = dataset_dir / rf
        assert p.is_file(), f"Expected test-pack file {p} does not exist"

