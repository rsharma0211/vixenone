import asyncio
from datetime import datetime, timezone
import logging
from typing import Callable, List, Optional
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import GeminiClientError, GeminiClientFactory, PageText
from app.models.evaluation import AnalysisJob, Document, DocumentPage, Evaluation, Requirement
from app.services.ingestion import DocumentExtractionError, extract_docx_pages
from app.services.storage import StorageService, get_storage

logger = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "Interrupted — please start again"
MAX_PARALLEL_DOCS = 4

SessionFactory = Callable[[], AsyncSession]
StorageFactory = Callable[[], StorageService]


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

    for desc in doc_descriptors:
        if desc["kind"] == "requirements":
            req_doc_id = desc["id"]
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
