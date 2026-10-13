from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import Document, Evaluation
from app.repositories.criteria_repo import CriteriaRepository
from app.repositories.evaluation_repo import EvaluationRepository
from app.schemas.criteria import BUILTIN_CRITERIA_DEFAULTS
from app.schemas.evaluation import (
    AnalysisJobResponse,
    CostBreakdownResponse,
    DocumentResponse,
    EvaluationDetailResponse,
    EvaluationResultsResponse,
    EvaluationSummaryResponse,
    FindingEvidence,
    FindingResponse,
    RequirementItem,
    VendorResponse,
    VendorResultItem,
    VendorTotalResult,
)
from app.services.document_validator import validate_document_content
from app.services.job_launcher import JobLauncher
from app.services.scoring import compute_vendor_scores, round_half_up
from app.services.storage import StorageService, get_storage


class EvaluationService:
    @staticmethod
    def _map_lifecycle_status(status: str) -> str:
        mapping = {
            "draft": "Draft",
            "requirements_review": "Requirements review",
            "analysed": "Analysed",
            "stale": "Stale",
        }
        return mapping.get(status, status.capitalize())

    @staticmethod
    async def get_summary_list(
        session: AsyncSession, user_id: uuid.UUID
    ) -> Dict[str, Any]:
        evaluations, kpis = await EvaluationRepository.list_by_user(session, user_id)
        items = []
        for e in evaluations:
            latest_job = e.jobs[0] if e.jobs else None
            reqs = e.requirements or []
            total_reqs = len(reqs)
            mandatory_reqs = sum(1 for r in reqs if r.mandatory)
            vendors_count = len(e.vendors or [])

            items.append(
                EvaluationSummaryResponse(
                    id=e.id,
                    title=e.title,
                    name=e.title,
                    name_short=e.title.split("—")[0].strip() if "—" in e.title else e.title,
                    category=e.category,
                    status=e.status,
                    lifecycle_status=EvaluationService._map_lifecycle_status(e.status),
                    vendors_count=vendors_count,
                    total_requirements=total_reqs,
                    mandatory_requirements=mandatory_reqs,
                    updated_at=e.updated_at,
                    created_at=e.created_at,
                    latest_job=AnalysisJobResponse.model_validate(latest_job) if latest_job else None,
                )
            )
        return {"evaluations": items, "kpis": kpis}

    @staticmethod
    async def get_detail(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> EvaluationDetailResponse:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )
        latest_job = eval_obj.jobs[0] if eval_obj.jobs else None
        return EvaluationDetailResponse(
            id=eval_obj.id,
            title=eval_obj.title,
            category=eval_obj.category,
            status=eval_obj.status,
            criteria_snapshot=eval_obj.criteria_snapshot,
            created_at=eval_obj.created_at,
            updated_at=eval_obj.updated_at,
            vendors=[VendorResponse.model_validate(v) for v in eval_obj.vendors],
            documents=[DocumentResponse.model_validate(d) for d in eval_obj.documents],
            requirements_count=len(eval_obj.requirements or []),
            latest_job=AnalysisJobResponse.model_validate(latest_job) if latest_job else None,
        )

    @staticmethod
    async def upload_document(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        file: UploadFile,
        kind: str,
        vendor_id: Optional[uuid.UUID] = None,
        storage: Optional[StorageService] = None,
    ) -> DocumentResponse:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )

        if await EvaluationRepository.has_active_job(session, evaluation_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot upload documents while a job is active for this evaluation",
            )

        if kind not in ("requirements", "proposal"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Kind must be 'requirements' or 'proposal'",
            )

        if kind == "proposal":
            if not vendor_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="vendor_id is required for proposal documents",
                )
            vendor_ids = {v.id for v in eval_obj.vendors}
            if vendor_id not in vendor_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Vendor {vendor_id} does not belong to this evaluation",
                )
        else:
            vendor_id = None

        content = await file.read()
        filename = file.filename or "document"

        # Content-based validation
        doc_type, mime, page_count = validate_document_content(content, filename)

        storage_service = storage or get_storage()

        # Check for existing document to replace
        conflicting = await EvaluationRepository.get_conflicting_document(
            session, evaluation_id, kind, vendor_id
        )
        old_doc_id = None
        if conflicting:
            old_doc_id = conflicting.id
            try:
                await storage_service.delete(conflicting.storage_key)
            except Exception:
                pass

        # Save new file via storage service
        file_uuid = uuid.uuid4()
        storage_key = f"evaluations/{evaluation_id}/{file_uuid}_{filename}"
        saved_key = await storage_service.save(storage_key, content)

        new_doc = Document(
            id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            vendor_id=vendor_id,
            kind=kind,
            filename=filename,
            mime=mime,
            size_bytes=len(content),
            storage_key=saved_key,
            page_count=page_count,
            status="uploaded",
        )

        saved_doc = await EvaluationRepository.replace_document(
            session, evaluation_id, new_doc, old_doc_id=old_doc_id
        )
        return DocumentResponse.model_validate(saved_doc)

    @staticmethod
    async def delete_document(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        doc_id: uuid.UUID,
        storage: Optional[StorageService] = None,
    ) -> None:
        doc = await EvaluationRepository.get_document(session, user_id, evaluation_id, doc_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {doc_id} not found",
            )
        if await EvaluationRepository.has_active_job(session, evaluation_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete documents while a job is active for this evaluation",
            )
        storage_service = storage or get_storage()
        try:
            await storage_service.delete(doc.storage_key)
        except Exception:
            pass
        await EvaluationRepository.delete_document(session, doc)

    @staticmethod
    async def add_vendor(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        name: str,
    ) -> VendorResponse:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )
        if await EvaluationRepository.has_active_job(session, evaluation_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot modify vendors while a job is active for this evaluation",
            )
        cleaned_name = name.strip()
        if not cleaned_name or len(cleaned_name) > 80:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vendor name must be between 1 and 80 characters.",
            )
        existing_vendors = sorted(eval_obj.vendors or [], key=lambda v: v.position)
        if len(existing_vendors) >= 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An evaluation can have at most 3 vendors.",
            )
        if any(v.name.strip().lower() == cleaned_name.lower() for v in existing_vendors):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Vendor '{cleaned_name}' already exists in this evaluation.",
            )
        next_position = len(existing_vendors)
        vendor = await EvaluationRepository.add_vendor(
            session, eval_obj, cleaned_name, next_position
        )
        return VendorResponse.model_validate(vendor)

    @staticmethod
    async def rename_vendor(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        vendor_id: uuid.UUID,
        name: str,
    ) -> VendorResponse:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )
        if await EvaluationRepository.has_active_job(session, evaluation_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot modify vendors while a job is active for this evaluation",
            )
        existing_vendors = eval_obj.vendors or []
        target_vendor = next((v for v in existing_vendors if v.id == vendor_id), None)
        if not target_vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor {vendor_id} not found",
            )
        cleaned_name = name.strip()
        if not cleaned_name or len(cleaned_name) > 80:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vendor name must be between 1 and 80 characters.",
            )
        if any(
            v.id != vendor_id and v.name.strip().lower() == cleaned_name.lower()
            for v in existing_vendors
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Vendor '{cleaned_name}' already exists in this evaluation.",
            )
        updated = await EvaluationRepository.rename_vendor(
            session, eval_obj, target_vendor, cleaned_name
        )
        return VendorResponse.model_validate(updated)

    @staticmethod
    async def delete_vendor(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        vendor_id: uuid.UUID,
        storage: Optional[StorageService] = None,
    ) -> None:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )
        if await EvaluationRepository.has_active_job(session, evaluation_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot modify vendors while a job is active for this evaluation",
            )
        target_vendor = next((v for v in (eval_obj.vendors or []) if v.id == vendor_id), None)
        if not target_vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor {vendor_id} not found",
            )
        storage_keys = await EvaluationRepository.delete_vendor(session, eval_obj, vendor_id)
        storage_service = storage or get_storage()
        for key in storage_keys:
            try:
                await storage_service.delete(key)
            except Exception:
                pass

    @staticmethod
    async def start_extraction(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        confirm_replace: bool,
        launcher: JobLauncher,
    ) -> AnalysisJobResponse:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )

        if await EvaluationRepository.has_active_job(session, evaluation_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A job is already active for this evaluation",
            )

        docs = eval_obj.documents or []
        has_req_doc = any(d.kind == "requirements" for d in docs)
        vendors = eval_obj.vendors or []
        proposal_vendor_ids = {
            d.vendor_id for d in docs if d.kind == "proposal" and d.vendor_id is not None
        }
        missing_vendors = [v.name for v in vendors if v.id not in proposal_vendor_ids]

        missing_reasons: List[str] = []
        if not has_req_doc:
            missing_reasons.append("Upload a requirements document.")
        if len(vendors) < 2:
            missing_reasons.append("Add at least 2 vendors.")
        for v_name in missing_vendors:
            missing_reasons.append(f"Upload a proposal for {v_name} or remove the vendor.")

        if missing_reasons:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=" ".join(missing_reasons),
            )

        reqs = eval_obj.requirements or []
        if not confirm_replace and any(r.origin == "user" for r in reqs):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User-edited requirements exist and edits will be replaced. Confirm replacement to proceed.",
            )

        job = await EvaluationRepository.create_job(
            session=session,
            evaluation_id=evaluation_id,
            kind="extract_requirements",
            step_label="Queued",
        )
        await launcher.launch(job.id)
        await session.refresh(job)
        return AnalysisJobResponse.model_validate(job)

    @staticmethod
    async def delete_evaluation(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        storage: Optional[StorageService] = None,
    ) -> None:
        storage_keys = await EvaluationRepository.delete(session, user_id, evaluation_id)
        if storage_keys is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )
        storage_service = storage or get_storage()
        for key in storage_keys:
            try:
                await storage_service.delete(key)
            except Exception:
                pass

    @staticmethod
    async def get_results(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> EvaluationResultsResponse:
        data = await EvaluationRepository.get_results_data(session, user_id, evaluation_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} not found",
            )

        eval_obj: Evaluation = data["evaluation"]
        if eval_obj.status not in ("analysed", "stale"):
            return EvaluationResultsResponse(
                status=eval_obj.status,
                vendors=[],
                findings=[],
                costs=[],
                clarifications={},
                scoring=[],
                vendor_totals={},
                recommendation=None,
            )

        vendors = data["vendors"]
        findings_raw = data["findings"]
        costs_raw = data["costs"]
        clarifications_raw = data["clarifications"]
        criterion_scores_raw = data["criterion_scores"]
        docs_map = data["docs_map"]

        # Determine criteria snapshot
        snapshot = eval_obj.criteria_snapshot
        if not snapshot:
            user_criteria = await CriteriaRepository.get_or_create_builtins(session, user_id)
            snapshot = [
                {
                    "key": c.builtin_key or f"custom:{c.id}",
                    "kind": c.kind,
                    "name": c.name,
                    "guidance": c.guidance,
                    "weight": c.weight,
                }
                for c in user_criteria
            ]

        # Group raw scores by (vendor_id, criterion_key)
        scores_by_vendor: Dict[str, Dict[str, Optional[Decimal]]] = {}
        for v in vendors:
            v_id_str = str(v.id)
            scores_by_vendor[v_id_str] = {}

        for cs in criterion_scores_raw:
            v_id_str = str(cs.vendor_id)
            if v_id_str in scores_by_vendor:
                scores_by_vendor[v_id_str][cs.criterion_key] = Decimal(str(cs.score))

        # Compute scores per vendor
        vendor_scoring_results: Dict[str, Dict[str, Any]] = {}
        for v in vendors:
            v_id_str = str(v.id)
            v_raw_scores = scores_by_vendor[v_id_str]
            vendor_scoring_results[v_id_str] = compute_vendor_scores(v_raw_scores, snapshot)

        # Build scoring matrix rows
        scoring_rows = []
        for item in snapshot:
            ckey = item["key"]
            row_vendor_scores = {}
            for v in vendors:
                v_id_str = str(v.id)
                cell_data = vendor_scoring_results[v_id_str]["criteria_scores"].get(ckey, {})
                sc = cell_data.get("score")
                pts = cell_data.get("points")
                raw_pts = cell_data.get("raw_points")
                row_vendor_scores[v_id_str] = {
                    "score": float(sc) if sc is not None else None,
                    "points": float(pts) if pts is not None else None,
                    "raw_points": float(raw_pts) if raw_pts is not None else None,
                }
            scoring_rows.append(
                {
                    "criterion": item["name"],
                    "criterion_key": ckey,
                    "weight": item["weight"],
                    "vendor_scores": row_vendor_scores,
                }
            )

        # Build vendor_totals map
        vendor_totals_map: Dict[str, VendorTotalResult] = {}
        for v in vendors:
            v_id_str = str(v.id)
            v_res = vendor_scoring_results[v_id_str]
            disp_tot = v_res["display_total"]
            raw_tot = v_res["raw_total"]
            vendor_totals_map[v_id_str] = VendorTotalResult(
                score=disp_tot,
                total=disp_tot,
                raw_score=float(raw_tot) if raw_tot is not None else None,
                raw_total=float(raw_tot) if raw_tot is not None else None,
                incomplete=v_res["incomplete"],
            )

        # Map findings with Evidence
        findings_response = []
        vendor_failures_count: Dict[str, int] = {str(v.id): 0 for v in vendors}
        vendor_unknown_count: Dict[str, int] = {str(v.id): 0 for v in vendors}
        vendor_needs_review_count: Dict[str, int] = {str(v.id): 0 for v in vendors}

        for f in findings_raw:
            v_id_str = str(f.vendor_id)
            if f.status == "Non-compliant":
                vendor_failures_count[v_id_str] = vendor_failures_count.get(v_id_str, 0) + 1
            if f.needs_review:
                vendor_needs_review_count[v_id_str] = vendor_needs_review_count.get(v_id_str, 0) + 1
            if "Unknown cost" in (f.risk_types or []):
                vendor_unknown_count[v_id_str] = vendor_unknown_count.get(v_id_str, 0) + 1

            evidence_obj = None
            if f.evidence_quote:
                doc_name = docs_map.get(f.evidence_document_id, "Proposal")
                evidence_obj = FindingEvidence(
                    quote=f.evidence_quote,
                    highlight=None,
                    document=doc_name,
                    page=f.evidence_page,
                    section=f.evidence_section,
                )

            fact_or_inference = "Inference" if f.is_inference else "Fact — directly quoted"

            findings_response.append(
                FindingResponse(
                    id=f.id,
                    evaluation_id=f.evaluation_id,
                    vendor_id=f.vendor_id,
                    requirement_id=f.requirement_id,
                    criterion_key=f.criterion_key,
                    status=f.status,
                    needs_review=f.needs_review,
                    inferred=f.is_inference,
                    confidence=f.confidence,
                    evidence_quote=f.evidence_quote,
                    evidence_document_id=f.evidence_document_id,
                    evidence_page=f.evidence_page,
                    evidence_section=f.evidence_section,
                    evidence=evidence_obj,
                    risk_types=f.risk_types or [],
                    severity=f.severity,
                    clarification_question=f.clarification_question,
                    fact_or_inference=fact_or_inference,
                )
            )

        # Map costs
        costs_by_vendor: Dict[str, CostBreakdownResponse] = {}
        costs_response = []
        for cb in costs_raw:
            v_id_str = str(cb.vendor_id)
            cb_resp = CostBreakdownResponse(
                id=cb.id,
                evaluation_id=cb.evaluation_id,
                vendor_id=cb.vendor_id,
                monthly_base=float(cb.monthly_base),
                gst_18=float(cb.gst_18),
                monthly_total=float(cb.monthly_total),
                included=cb.included or [],
                excluded=cb.excluded or [],
                optional=cb.optional or [],
                unknown=cb.unknown or [],
            )
            costs_by_vendor[v_id_str] = cb_resp
            costs_response.append(cb_resp)

        # Clarifications
        clarifications_map: Dict[str, List[str]] = {str(v.id): [] for v in vendors}
        for cl in clarifications_raw:
            v_id_str = str(cl.vendor_id)
            if not cl.answered:
                clarifications_map.setdefault(v_id_str, []).append(cl.question)

        # Build vendor items
        vendor_items = []
        for v in vendors:
            v_id_str = str(v.id)
            cost_obj = costs_by_vendor.get(v_id_str)
            tot_res = vendor_totals_map[v_id_str]
            vendor_items.append(
                VendorResultItem(
                    id=v_id_str,
                    name=v.name,
                    score=tot_res.total,
                    raw_score=tot_res.raw_total,
                    mandatory_failures=vendor_failures_count.get(v_id_str, 0),
                    monthly_base_inr=cost_obj.monthly_base if cost_obj else 0.0,
                    gst_rate=0.18,
                    monthly_gst_inr=cost_obj.gst_18 if cost_obj else 0.0,
                    monthly_total_inr=cost_obj.monthly_total if cost_obj else 0.0,
                    unknown_costs_count=len(cost_obj.unknown) if cost_obj else 0,
                    needs_review_count=vendor_needs_review_count.get(v_id_str, 0),
                )
            )

        return EvaluationResultsResponse(
            status=eval_obj.status,
            vendors=vendor_items,
            findings=findings_response,
            costs=costs_response,
            clarifications=clarifications_map,
            scoring=scoring_rows,
            vendor_totals=vendor_totals_map,
            recommendation=None,
        )
