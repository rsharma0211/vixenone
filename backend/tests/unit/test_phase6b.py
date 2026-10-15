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


def _build_content_based_fake_gemini(dataset_dir: Path) -> FakeGeminiClient:
    """Create a FakeGeminiClient that makes decisions based on content, not call order."""
    def pdf_handler(pdf_bytes: bytes) -> List[PageText]:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return [
                PageText(page_number=idx, text=p.extract_text() or "")
                for idx, p in enumerate(pdf.pages, start=1)
            ]

    def requirements_handler(pages: List[PageText]) -> List[ExtractedRequirement]:
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

        if "brightnest" in v_lower:
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
