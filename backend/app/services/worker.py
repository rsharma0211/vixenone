import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional, cast
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import (
    GeminiClientError,
    GeminiClientFactory,
    PageText,
    VendorAnalysisResult,
)
from app.models.criteria import EvaluationCriterion
from app.models.evaluation import (
    AnalysisJob,
    Clarification,
    CostBreakdown,
    CriterionScore,
    Document,
    DocumentPage,
    Evaluation,
    Finding,
    Requirement,
    Vendor,
)
from app.schemas.criteria import BUILTIN_CRITERIA_DEFAULTS
from app.services.ingestion import extract_docx_pages
from app.services.scoring import (
    compute_cost_amounts,
    compute_raw_criterion_scores,
    deduplicate_clarifications,
)
from app.services.storage import StorageService, get_storage
from app.services.verification import verify_quote_against_pages

logger = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "Interrupted — please start again"
MAX_PARALLEL_DOCS = 4

SessionFactory = Callable[[], AsyncSession]
StorageFactory = Callable[[], StorageService]

_STATUS_DISPLAY_MAP = {
    "compliant": "Compliant",
    "partially_compliant": "Partially compliant",
    "partial": "Partially compliant",
    "non_compliant": "Non-compliant",
    "noncompliant": "Non-compliant",
    "not_evidenced": "Not evidenced",
    "notevidenced": "Not evidenced",
}

_RISK_DISPLAY_MAP = {
    "exclusion": "Exclusion",
    "omission": "Omission",
    "ambiguity": "Ambiguity",
    "contradiction": "Contradiction",
    "unknown_cost": "Unknown cost",
}

_LEVEL_DISPLAY_MAP = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def _map_status_display(val: Any) -> str:
    raw = getattr(val, "value", val)
    key = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _STATUS_DISPLAY_MAP.get(key, "Not evidenced")


def _map_risk_types_display(risks: Optional[List[Any]]) -> List[str]:
    result: List[str] = []
    for r in risks or []:
        raw = getattr(r, "value", r)
        key = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
        mapped = _RISK_DISPLAY_MAP.get(key)
        if mapped and mapped not in result:
            result.append(mapped)
    return result


def _map_level_display(
    val: Any, default: Optional[str] = None
) -> Optional[str]:
    if val is None:
        return default
    raw = getattr(val, "value", val)
    key = str(raw or "").strip().lower()
    return _LEVEL_DISPLAY_MAP.get(key, default)


def _format_user_error(exc: BaseException, default_msg: str) -> str:
    msg = str(exc).strip()
    if msg:
        return msg[:300]
    return default_msg


async def recover_interrupted_jobs(session_factory: SessionFactory) -> None:
    """Mark any in-flight jobs or documents as interrupted on startup."""
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        job_stmt = (
            update(AnalysisJob)
            .where(AnalysisJob.status.in_(["queued", "extracting", "analysing"]))
            .values(
                status="failed",
                error_message=INTERRUPTED_MESSAGE,
                finished_at=now,
                updated_at=now,
            )
        )
        doc_stmt = (
            update(Document)
            .where(Document.status == "extracting")
            .values(
                status="error",
                error_message=INTERRUPTED_MESSAGE,
                updated_at=now,
            )
        )
        await session.execute(job_stmt)
        await session.execute(doc_stmt)
        await session.commit()


async def run_job_by_id(
    job_id: uuid.UUID,
    session_factory: SessionFactory,
    gemini_client_factory: GeminiClientFactory,
    storage_factory: Optional[StorageFactory] = None,
) -> None:
    """Isolated worker entry point. Runs a background job using only its ID and factories."""
    resolved_storage_factory = storage_factory or get_storage

    async with session_factory() as session:
        job = await session.get(AnalysisJob, job_id)
        if job is None:
            logger.warning("Worker invoked for missing job_id=%s", job_id)
            return
        evaluation_id = job.evaluation_id
        job_kind = job.kind

    try:
        if job_kind == "extract_requirements":
            await _run_extract_requirements(
                job_id=job_id,
                evaluation_id=evaluation_id,
                session_factory=session_factory,
                gemini_client_factory=gemini_client_factory,
                storage_factory=resolved_storage_factory,
            )
        elif job_kind == "analyse":
            await _run_analyse(
                job_id=job_id,
                evaluation_id=evaluation_id,
                session_factory=session_factory,
                gemini_client_factory=gemini_client_factory,
            )
        else:
            await _mark_job_failed(
                session_factory,
                job_id,
                f"Unsupported job kind: {job_kind}",
            )
    except Exception as exc:
        logger.error(
            "Unhandled error in worker for job_id=%s error_type=%s",
            job_id,
            type(exc).__name__,
        )
        await _mark_job_failed(
            session_factory,
            job_id,
            _format_user_error(exc, "Job failed due to an unexpected error"),
        )


async def _mark_job_failed(
    session_factory: SessionFactory,
    job_id: uuid.UUID,
    error_message: str,
) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        job = await session.get(AnalysisJob, job_id)
        if job is not None and job.status not in ("done", "failed"):
            job.status = "failed"
            job.error_message = error_message
            job.finished_at = now
            job.updated_at = now
            await session.commit()


async def _run_extract_requirements(
    job_id: uuid.UUID,
    evaluation_id: uuid.UUID,
    session_factory: SessionFactory,
    gemini_client_factory: GeminiClientFactory,
    storage_factory: StorageFactory,
) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        docs_stmt = (
            select(Document)
            .where(Document.evaluation_id == evaluation_id)
            .order_by(Document.created_at, Document.id)
        )
        docs_res = await session.execute(docs_stmt)
        docs = list(docs_res.scalars().all())
        total_docs = len(docs)

        doc_descriptors = [
            {
                "id": d.id,
                "kind": d.kind,
                "mime": d.mime,
                "filename": d.filename,
                "storage_key": d.storage_key,
                "page_count": d.page_count,
            }
            for d in docs
        ]

        job = await session.get(AnalysisJob, job_id)
        if job is None:
            return
        job.status = "extracting"
        job.started_at = now
        job.step_label = f"Reading documents 0 of {total_docs}"
        job.error_message = None
        job.updated_at = now

        for d in docs:
            d.status = "extracting"
            d.error_message = None
            d.updated_at = now

        await session.commit()

    if total_docs == 0:
        await _mark_job_failed(
            session_factory, job_id, "No documents found for evaluation"
        )
        return

    semaphore = asyncio.Semaphore(MAX_PARALLEL_DOCS)
    progress_lock = asyncio.Lock()
    completed_count = 0
    req_doc_error: Optional[str] = None
    req_doc_id: Optional[uuid.UUID] = None

    # Ensure requirements doc is processed first deterministically
    doc_descriptors = sorted(
        doc_descriptors, key=lambda d: (0 if d["kind"] == "requirements" else 1)
    )

    for desc in doc_descriptors:
        if desc["kind"] == "requirements":
            raw_id = desc["id"]
            req_doc_id = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
            break

    if req_doc_id is None:
        await _mark_job_failed(
            session_factory, job_id, "Requirements document is missing"
        )
        return

    gemini_client = gemini_client_factory()
    storage = storage_factory()

    async def _process_one_document(desc: dict) -> None:
        nonlocal completed_count, req_doc_error
        doc_id: uuid.UUID = desc["id"]
        doc_kind: str = desc["kind"]
        doc_mime: str = desc["mime"]
        storage_key: str = desc["storage_key"]

        async with semaphore:
            try:
                file_bytes = await storage.read(storage_key)
                is_pdf = (
                    doc_mime == "application/pdf"
                    or storage_key.lower().endswith(".pdf")
                )
                if is_pdf:
                    pages = await gemini_client.pdf_to_pages(file_bytes)
                else:
                    pages = extract_docx_pages(file_bytes)

                if not pages:
                    raise GeminiClientError("Document produced no readable pages")

                async with session_factory() as doc_session:
                    await doc_session.execute(
                        delete(DocumentPage).where(
                            DocumentPage.document_id == doc_id
                        )
                    )
                    for p in pages:
                        doc_session.add(
                            DocumentPage(
                                id=uuid.uuid4(),
                                document_id=doc_id,
                                page_number=p.page_number,
                                text=p.text,
                            )
                        )
                    doc_row = await doc_session.get(Document, doc_id)
                    if doc_row is not None:
                        doc_row.status = "ready"
                        doc_row.error_message = None
                        if not doc_row.page_count:
                            doc_row.page_count = len(pages)
                        doc_row.updated_at = datetime.now(timezone.utc)
                    await doc_session.commit()

            except Exception as exc:
                err_msg = _format_user_error(
                    exc, "Failed to extract text from document"
                )
                logger.warning(
                    "Document extraction failed: doc_id=%s kind=%s error_type=%s",
                    doc_id,
                    doc_kind,
                    type(exc).__name__,
                )
                async with session_factory() as doc_session:
                    doc_row = await doc_session.get(Document, doc_id)
                    if doc_row is not None:
                        doc_row.status = "error"
                        doc_row.error_message = err_msg
                        doc_row.updated_at = datetime.now(timezone.utc)
                    await doc_session.commit()
                if doc_kind == "requirements":
                    req_doc_error = err_msg

            finally:
                async with progress_lock:
                    completed_count += 1
                    current_done = completed_count
                    async with session_factory() as prog_session:
                        j = await prog_session.get(AnalysisJob, job_id)
                        if j is not None and j.status == "extracting":
                            j.step_label = (
                                f"Reading documents {current_done} of {total_docs}"
                            )
                            j.updated_at = datetime.now(timezone.utc)
                            await prog_session.commit()

    await asyncio.gather(*(_process_one_document(d) for d in doc_descriptors))

    if req_doc_error is not None:
        await _mark_job_failed(
            session_factory,
            job_id,
            f"Requirements document extraction failed: {req_doc_error}",
        )
        return

    # Update step label to "Finding requirements"
    async with session_factory() as session:
        job = await session.get(AnalysisJob, job_id)
        if job is not None:
            job.step_label = "Finding requirements"
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()

        pages_stmt = (
            select(DocumentPage)
            .where(DocumentPage.document_id == req_doc_id)
            .order_by(DocumentPage.page_number)
        )
        pages_res = await session.execute(pages_stmt)
        stored_pages = list(pages_res.scalars().all())
        req_doc_row = await session.get(Document, req_doc_id)
        max_page = (
            req_doc_row.page_count
            if req_doc_row and req_doc_row.page_count
            else len(stored_pages)
        )

    page_models = [
        PageText(page_number=p.page_number, text=p.text) for p in stored_pages
    ]

    try:
        extracted_reqs = await gemini_client.extract_requirements(page_models)
    except Exception as exc:
        err_msg = _format_user_error(
            exc, "Failed to extract requirements from document"
        )
        await _mark_job_failed(session_factory, job_id, err_msg)
        return

    # Replace all requirements for the evaluation in one transaction
    finish_now = datetime.now(timezone.utc)
    async with session_factory() as session:
        await session.execute(
            delete(Requirement).where(Requirement.evaluation_id == evaluation_id)
        )

        for idx, item in enumerate(extracted_reqs):
            raw_code = (item.code or "").strip()
            code = raw_code if raw_code else f"R{idx + 1}"
            source_page = item.source_page
            if (
                source_page is None
                or source_page < 1
                or (max_page > 0 and source_page > max_page)
            ):
                source_page = None

            req_row = Requirement(
                id=uuid.uuid4(),
                evaluation_id=evaluation_id,
                code=code,
                text=item.text.strip() if item.text else f"Requirement {code}",
                category=(item.category or "").strip() or "General",
                mandatory=bool(item.mandatory),
                acceptance=(item.acceptance or "").strip(),
                source_document_id=req_doc_id,
                source_page=source_page,
                source_section=(
                    item.source_section.strip()
                    if item.source_section and item.source_section.strip()
                    else None
                ),
                position=idx,
                origin="extracted",
            )
            session.add(req_row)

        eval_obj = await session.get(Evaluation, evaluation_id)
        if eval_obj is not None:
            eval_obj.status = "requirements_review"
            eval_obj.updated_at = finish_now

        job = await session.get(AnalysisJob, job_id)
        if job is not None:
            job.status = "done"
            job.finished_at = finish_now
            job.updated_at = finish_now

        await session.commit()


async def _run_analyse(
    job_id: uuid.UUID,
    evaluation_id: uuid.UUID,
    session_factory: SessionFactory,
    gemini_client_factory: GeminiClientFactory,
) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        eval_obj = await session.get(Evaluation, evaluation_id)
        if eval_obj is None:
            await _mark_job_failed(
                session_factory, job_id, "Evaluation not found"
            )
            return

        v_stmt = (
            select(Vendor)
            .where(Vendor.evaluation_id == evaluation_id)
            .order_by(Vendor.position, Vendor.id)
        )
        vendors = list((await session.execute(v_stmt)).scalars().all())
        total_vendors = len(vendors)

        r_stmt = (
            select(Requirement)
            .where(Requirement.evaluation_id == evaluation_id)
            .order_by(Requirement.position, Requirement.code)
        )
        requirements = list((await session.execute(r_stmt)).scalars().all())

        d_stmt = select(Document).where(
            Document.evaluation_id == evaluation_id,
            Document.kind == "proposal",
        )
        proposal_docs = list((await session.execute(d_stmt)).scalars().all())
        proposal_by_vendor: Dict[uuid.UUID, Document] = {
            d.vendor_id: d for d in proposal_docs if d.vendor_id is not None
        }

        doc_ids = [d.id for d in proposal_docs]
        pages_by_doc: Dict[uuid.UUID, List[PageText]] = {
            d.id: [] for d in proposal_docs
        }
        if doc_ids:
            p_stmt = (
                select(DocumentPage)
                .where(DocumentPage.document_id.in_(doc_ids))
                .order_by(DocumentPage.page_number)
            )
            for p_row in (await session.execute(p_stmt)).scalars().all():
                pages_by_doc.setdefault(p_row.document_id, []).append(
                    PageText(page_number=p_row.page_number, text=p_row.text)
                )

        criteria_snapshot = eval_obj.criteria_snapshot
        if not criteria_snapshot:
            c_stmt = (
                select(EvaluationCriterion)
                .where(EvaluationCriterion.user_id == eval_obj.user_id)
                .order_by(
                    EvaluationCriterion.position,
                    EvaluationCriterion.created_at,
                )
            )
            user_criteria = list((await session.execute(c_stmt)).scalars().all())
            if user_criteria:
                criteria_snapshot = [
                    {
                        "key": c.builtin_key
                        if c.kind == "builtin" and c.builtin_key
                        else f"custom:{c.id}",
                        "kind": c.kind,
                        "name": c.name,
                        "guidance": c.guidance,
                        "weight": int(c.weight),
                    }
                    for c in user_criteria
                ]
            else:
                criteria_snapshot = [
                    {
                        "key": b_key,
                        "kind": "builtin",
                        "name": b_data["name"],
                        "guidance": b_data["guidance"],
                        "weight": b_data["default_weight"],
                    }
                    for b_key, b_data in sorted(
                        BUILTIN_CRITERIA_DEFAULTS.items(),
                        key=lambda kv: cast(int, kv[1]["position"]),
                    )
                ]
            eval_obj.criteria_snapshot = criteria_snapshot

        vendor_descriptors = []
        for v in vendors:
            p_doc = proposal_by_vendor.get(v.id)
            p_pages = pages_by_doc.get(p_doc.id, []) if p_doc else []
            vendor_descriptors.append(
                {
                    "id": v.id,
                    "name": v.name,
                    "position": v.position,
                    "doc_id": p_doc.id if p_doc else None,
                    "pages": p_pages,
                }
            )

        req_descriptors = [
            {
                "id": r.id,
                "code": r.code,
                "text": r.text,
                "category": r.category,
                "mandatory": r.mandatory,
                "acceptance": r.acceptance,
            }
            for r in requirements
        ]

        job = await session.get(AnalysisJob, job_id)
        if job is None:
            return
        job.status = "analysing"
        job.started_at = now
        job.step_label = f"Analysing vendor 1 of {max(1, total_vendors)}"
        job.error_message = None
        job.updated_at = now
        await session.commit()

    if total_vendors < 2 or not req_descriptors:
        await _mark_job_failed(
            session_factory,
            job_id,
            "Analysis preconditions not met (need >=2 vendors and >=1 requirement)",
        )
        return

    judged_criteria = [
        c
        for c in criteria_snapshot
        if c["key"] in ("service_coverage", "sla_operational")
        or c.get("kind") == "custom"
        or str(c["key"]).startswith("custom:")
    ]

    gemini_client = gemini_client_factory()
    semaphore = asyncio.Semaphore(MAX_PARALLEL_DOCS)
    progress_lock = asyncio.Lock()
    completed_count = 0
    vendor_results: Dict[uuid.UUID, VendorAnalysisResult] = {}
    vendor_errors: List[str] = []

    async def _analyse_one_vendor(v_desc: Dict[str, Any]) -> None:
        nonlocal completed_count
        v_id: uuid.UUID = v_desc["id"]
        v_name: str = v_desc["name"]
        v_pages: List[PageText] = v_desc["pages"]

        async with semaphore:
            try:
                res = await gemini_client.analyse_vendor(
                    vendor_name=v_name,
                    requirements=req_descriptors,
                    judged_criteria=judged_criteria,
                    pages=v_pages,
                )
                vendor_results[v_id] = res
            except Exception as exc:
                err_msg = _format_user_error(
                    exc, f"Failed to analyse vendor {v_name}"
                )
                logger.warning(
                    "Vendor analysis failed: vendor_id=%s error_type=%s",
                    v_id,
                    type(exc).__name__,
                )
                vendor_errors.append(f"{v_name}: {err_msg}")
            finally:
                async with progress_lock:
                    completed_count += 1
                    current_step = min(completed_count, total_vendors)
                    async with session_factory() as prog_session:
                        j = await prog_session.get(AnalysisJob, job_id)
                        if j is not None and j.status == "analysing":
                            j.step_label = (
                                f"Analysing vendor {current_step} of {total_vendors}"
                            )
                            j.updated_at = datetime.now(timezone.utc)
                            await prog_session.commit()

    await asyncio.gather(*(_analyse_one_vendor(vd) for vd in vendor_descriptors))

    # All-or-nothing: if any vendor failed, fail job and leave existing DB results untouched
    if vendor_errors or len(vendor_results) != total_vendors:
        combined_err = (
            "; ".join(vendor_errors)
            if vendor_errors
            else "One or more vendors failed analysis"
        )
        await _mark_job_failed(session_factory, job_id, combined_err[:300])
        return

    # Prepare all DB objects in Python before opening the write transaction
    new_findings: List[Finding] = []
    new_costs: List[CostBreakdown] = []
    new_clarifications: List[Clarification] = []
    new_scores: List[CriterionScore] = []

    judged_keys_set = {c["key"] for c in judged_criteria}

    for v_desc in vendor_descriptors:
        v_id = cast(uuid.UUID, v_desc["id"])
        doc_id: Optional[uuid.UUID] = cast(Optional[uuid.UUID], v_desc["doc_id"])
        v_pages: List[PageText] = cast(List[PageText], v_desc["pages"])
        v_analysis = vendor_results[v_id]

        # Index requirement findings by normalised code
        rf_by_code = {
            (rf.code or "").strip().lower(): rf
            for rf in v_analysis.requirement_findings
            if rf.code
        }

        mandatory_statuses: List[str] = []
        vendor_risk_items: List[Dict[str, Any]] = []
        vendor_questions: List[Optional[str]] = []

        for r_desc in req_descriptors:
            r_id: uuid.UUID = cast(uuid.UUID, r_desc["id"])
            r_code: str = cast(str, r_desc["code"])
            r_mand: bool = bool(r_desc["mandatory"])
            rf = rf_by_code.get(r_code.strip().lower())

            if rf is not None:
                status_display = _map_status_display(rf.status)
                raw_quote = rf.quote
                raw_page = rf.page
                raw_section = (
                    rf.section.strip()
                    if rf.section and rf.section.strip()
                    else None
                )
                confidence_display = (
                    _map_level_display(rf.confidence, default="High") or "High"
                )
                is_inf = bool(rf.is_inference)
                risk_types_display = _map_risk_types_display(rf.risk_types)
                severity_display = _map_level_display(
                    rf.severity,
                    default="Medium" if risk_types_display else None,
                )
                clarif_q = (
                    rf.clarification_question.strip()
                    if rf.clarification_question
                    and rf.clarification_question.strip()
                    else None
                )
            else:
                status_display = "Not evidenced"
                raw_quote = None
                raw_page = None
                raw_section = None
                confidence_display = "Low"
                is_inf = True
                risk_types_display = []
                severity_display = None
                clarif_q = f"Please confirm compliance with {r_code}."

            verified_quote, verified_page, needs_review = (
                verify_quote_against_pages(
                    status=status_display,
                    quote=raw_quote,
                    cited_page=raw_page,
                    pages=v_pages,
                )
            )

            if r_mand:
                mandatory_statuses.append(status_display)

            if risk_types_display:
                vendor_risk_items.append(
                    {
                        "risk_types": risk_types_display,
                        "severity": severity_display or "Medium",
                    }
                )

            if clarif_q:
                vendor_questions.append(clarif_q)

            new_findings.append(
                Finding(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    vendor_id=v_id,
                    requirement_id=r_id,
                    criterion_key=None,
                    status=status_display,
                    needs_review=needs_review,
                    is_inference=is_inf,
                    confidence=confidence_display,
                    evidence_quote=verified_quote,
                    evidence_document_id=doc_id if verified_quote else None,
                    evidence_page=verified_page,
                    evidence_section=raw_section,
                    risk_types=risk_types_display,
                    severity=severity_display,
                    clarification_question=clarif_q,
                )
            )

        # Criterion findings (reference snapshot key only)
        cf_by_key = {
            (cf.key or "").strip(): cf
            for cf in v_analysis.criterion_findings
            if cf.key
        }
        criterion_status_by_key: Dict[str, Optional[str]] = {}
        for j_key in judged_keys_set:
            cf = cf_by_key.get(j_key)
            if cf is not None:
                c_status_display = _map_status_display(cf.status)
                criterion_status_by_key[j_key] = c_status_display
                v_quote, v_page, c_needs_review = verify_quote_against_pages(
                    status=c_status_display,
                    quote=cf.quote,
                    cited_page=cf.page,
                    pages=v_pages,
                )
                c_section = (
                    cf.section.strip()
                    if cf.section and cf.section.strip()
                    else None
                )
                new_findings.append(
                    Finding(
                        id=uuid.uuid4(),
                        evaluation_id=evaluation_id,
                        vendor_id=v_id,
                        requirement_id=None,
                        criterion_key=j_key,
                        status=c_status_display,
                        needs_review=c_needs_review,
                        is_inference=False,
                        confidence="High",
                        evidence_quote=v_quote,
                        evidence_document_id=doc_id if v_quote else None,
                        evidence_page=v_page,
                        evidence_section=c_section,
                        risk_types=[],
                        severity=None,
                        clarification_question=None,
                    )
                )
            else:
                criterion_status_by_key[j_key] = None

        # Standalone risks not tied to a requirement
        for sr in v_analysis.risks:
            sr_risks_display = _map_risk_types_display(sr.risk_types)
            sr_sev_display = (
                _map_level_display(sr.severity, default="Medium") or "Medium"
            )
            sr_quote, sr_page, sr_needs_review = verify_quote_against_pages(
                status="non_compliant" if sr.quote else "not_evidenced",
                quote=sr.quote,
                cited_page=sr.page,
                pages=v_pages,
            )
            sr_section = (
                sr.section.strip()
                if sr.section and sr.section.strip()
                else None
            )
            sr_q = (
                sr.clarification_question.strip()
                if sr.clarification_question
                and sr.clarification_question.strip()
                else None
            )
            if sr_risks_display:
                vendor_risk_items.append(
                    {
                        "risk_types": sr_risks_display,
                        "severity": sr_sev_display,
                    }
                )
            if sr_q:
                vendor_questions.append(sr_q)

            new_findings.append(
                Finding(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    vendor_id=v_id,
                    requirement_id=None,
                    criterion_key=None,
                    status="Not evidenced",
                    needs_review=sr_needs_review,
                    is_inference=not bool(sr_quote),
                    confidence="Medium",
                    evidence_quote=sr_quote,
                    evidence_document_id=doc_id if sr_quote else None,
                    evidence_page=sr_page,
                    evidence_section=sr_section,
                    risk_types=sr_risks_display,
                    severity=sr_sev_display,
                    clarification_question=sr_q,
                )
            )

        # Costs (Python computes exact GST and monthly_total)
        raw_included = [
            x.item.strip()
            for x in v_analysis.cost.included
            if x.item and x.item.strip()
        ]
        raw_excluded = [
            x.item.strip()
            for x in v_analysis.cost.excluded
            if x.item and x.item.strip()
        ]
        raw_optional = [
            x.item.strip()
            for x in v_analysis.cost.optional
            if x.item and x.item.strip()
        ]
        raw_unknown = [
            x.item.strip()
            for x in v_analysis.cost.unknown
            if x.item and x.item.strip()
        ]

        # Clarifications (deduplicated per vendor on normalised text, answered = False)
        deduped_questions = deduplicate_clarifications(vendor_questions)
        for q_text in deduped_questions:
            new_clarifications.append(
                Clarification(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    vendor_id=v_id,
                    question=q_text,
                    answered=False,
                )
            )

        # Criterion scores (raw 0-100 score for every snapshot key)
        # Cost comparability is computed from the extracted unknown list BEFORE appending display placeholder
        raw_scores_map = compute_raw_criterion_scores(
            criteria_snapshot=criteria_snapshot,
            mandatory_statuses=mandatory_statuses,
            criterion_findings_by_key=criterion_status_by_key,
            monthly_base=v_analysis.cost.monthly_base,
            unknown_items=raw_unknown,
            findings_and_risks=vendor_risk_items,
        )
        for c_key, c_score in raw_scores_map.items():
            new_scores.append(
                CriterionScore(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    vendor_id=v_id,
                    criterion_key=c_key,
                    score=c_score,
                )
            )

        # Cost breakdown (append display placeholder to stored unknown list if base not stated)
        cost_calc = compute_cost_amounts(
            monthly_base=v_analysis.cost.monthly_base,
            unknown_items=raw_unknown,
        )
        new_costs.append(
            CostBreakdown(
                id=uuid.uuid4(),
                evaluation_id=evaluation_id,
                vendor_id=v_id,
                monthly_base=cost_calc["monthly_base"],
                gst_18=cost_calc["gst_18"],
                monthly_total=cost_calc["monthly_total"],
                included=raw_included,
                excluded=raw_excluded,
                optional=raw_optional,
                unknown=cost_calc["unknown"],
            )
        )

    # Write all vendors in one transaction
    finish_now = datetime.now(timezone.utc)
    async with session_factory() as session:
        await session.execute(
            delete(Finding).where(Finding.evaluation_id == evaluation_id)
        )
        await session.execute(
            delete(CostBreakdown).where(
                CostBreakdown.evaluation_id == evaluation_id
            )
        )
        await session.execute(
            delete(Clarification).where(
                Clarification.evaluation_id == evaluation_id
            )
        )
        await session.execute(
            delete(CriterionScore).where(
                CriterionScore.evaluation_id == evaluation_id
            )
        )

        session.add_all(new_findings)
        session.add_all(new_costs)
        session.add_all(new_clarifications)
        session.add_all(new_scores)

        eval_obj = await session.get(Evaluation, evaluation_id)
        if eval_obj is not None:
            eval_obj.status = "analysed"
            eval_obj.updated_at = finish_now

        job = await session.get(AnalysisJob, job_id)
        if job is not None:
            job.status = "done"
            job.step_label = f"Analysing vendor {total_vendors} of {total_vendors}"
            job.finished_at = finish_now
            job.updated_at = finish_now

        await session.commit()
