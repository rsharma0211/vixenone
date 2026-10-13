from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evaluation import (
    AnalysisJob,
    Clarification,
    CostBreakdown,
    CriterionScore,
    Document,
    Evaluation,
    Finding,
    Requirement,
    Vendor,
)
from app.schemas.evaluation import EvaluationStatus, RequirementItem


class EvaluationRepository:
    @staticmethod
    async def get_by_id(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> Optional[Evaluation]:
        stmt = (
            select(Evaluation)
            .where(Evaluation.id == evaluation_id, Evaluation.user_id == user_id)
            .options(
                selectinload(Evaluation.vendors),
                selectinload(Evaluation.documents),
                selectinload(Evaluation.requirements),
                selectinload(Evaluation.jobs),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        session: AsyncSession, user_id: uuid.UUID
    ) -> Tuple[List[Evaluation], Dict[str, int]]:
        stmt = (
            select(Evaluation)
            .where(Evaluation.user_id == user_id)
            .options(
                selectinload(Evaluation.vendors),
                selectinload(Evaluation.requirements),
                selectinload(Evaluation.jobs),
            )
            .order_by(desc(Evaluation.updated_at))
        )
        res = await session.execute(stmt)
        evaluations = list(res.scalars().all())

        # KPIs
        total = len(evaluations)
        needs_action = sum(
            1 for e in evaluations if e.status in (EvaluationStatus.REQUIREMENTS_REVIEW.value, EvaluationStatus.STALE.value)
        )
        analysed = sum(1 for e in evaluations if e.status == EvaluationStatus.ANALYSED.value)

        # Open clarifications for user across all their evaluations
        eval_ids = [e.id for e in evaluations]
        open_clarifications = 0
        if eval_ids:
            clarif_stmt = (
                select(func.count(Clarification.id))
                .where(
                    Clarification.evaluation_id.in_(eval_ids),
                    Clarification.answered.is_(False),
                )
            )
            clarif_res = await session.execute(clarif_stmt)
            open_clarifications = clarif_res.scalar() or 0

        kpis = {
            "total": total,
            "needs_action": needs_action,
            "analysed":光明 if False else analysed,
            "open_clarifications": open_clarifications,
        }
        return evaluations, kpis

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        category: str,
        vendor_names: List[str],
    ) -> Evaluation:
        eval_obj = Evaluation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            category=category,
            status=EvaluationStatus.DRAFT.value,
        )
        session.add(eval_obj)

        for pos, name in enumerate(vendor_names):
            vendor = Vendor(
                id=uuid.uuid4(),
                evaluation_id=eval_obj.id,
                name=name,
                position=pos,
            )
            session.add(vendor)

        await session.commit()
        return await EvaluationRepository.get_by_id(session, user_id, eval_obj.id)

    @staticmethod
    async def update(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        title: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Evaluation]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None

        if title is not None:
            eval_obj.title = title
        if category is not None:
            eval_obj.category = category
        if status is not None:
            eval_obj.status = status
        eval_obj.updated_at = func.now()

        await session.commit()
        return await EvaluationRepository.get_by_id(session, user_id, evaluation_id)

    @staticmethod
    async def delete(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> Optional[List[str]]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None

        storage_keys = [doc.storage_key for doc in eval_obj.documents]

        await session.delete(eval_obj)
        await session.commit()
        return storage_keys

    @staticmethod
    async def get_document(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID, doc_id: uuid.UUID
    ) -> Optional[Document]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None

        stmt = select(Document).where(
            Document.id == doc_id, Document.evaluation_id == evaluation_id
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_conflicting_document(
        session: AsyncSession,
        evaluation_id: uuid.UUID,
        kind: str,
        vendor_id: Optional[uuid.UUID],
    ) -> Optional[Document]:
        if kind == "requirements":
            stmt = select(Document).where(
                Document.evaluation_id == evaluation_id, Document.kind == "requirements"
            )
        else:
            stmt = select(Document).where(
                Document.evaluation_id == evaluation_id,
                Document.kind == "proposal",
                Document.vendor_id == vendor_id,
            )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def replace_document(
        session: AsyncSession,
        evaluation_id: uuid.UUID,
        new_doc: Document,
        old_doc_id: Optional[uuid.UUID] = None,
    ) -> Document:
        if old_doc_id:
            await session.execute(delete(Document).where(Document.id == old_doc_id))
        session.add(new_doc)
        await session.commit()
        await session.refresh(new_doc)
        return new_doc

    @staticmethod
    async def delete_document(
        session: AsyncSession, doc: Document
    ) -> None:
        await session.delete(doc)
        await session.commit()

    @staticmethod
    async def get_requirements(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> Optional[List[Requirement]]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None
        stmt = (
            select(Requirement)
            .where(Requirement.evaluation_id == evaluation_id)
            .order_by(Requirement.position, Requirement.code)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def replace_requirements(
        session: AsyncSession,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        items: List[RequirementItem],
    ) -> Optional[List[Requirement]]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None

        # Validate unique codes (case-insensitive) before any DB writes
        codes_seen = set()
        for item in items:
            low_code = item.code.strip().lower()
            if low_code in codes_seen:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Duplicate requirement code: '{item.code}'",
                )
            codes_seen.add(low_code)

        # Atomically delete existing requirements
        await session.execute(
            delete(Requirement).where(Requirement.evaluation_id == evaluation_id)
        )

        # Insert new
        new_reqs = []
        for pos, item in enumerate(items):
            r = Requirement(
                id=item.id or uuid.uuid4(),
                evaluation_id=evaluation_id,
                code=item.code,
                text=item.text,
                category=item.category,
                mandatory=item.mandatory,
                acceptance=item.acceptance,
                source_document_id=item.source_document_id,
                source_page=item.source_page,
                source_section=item.source_section,
                position=item.position if item.position is not None else pos,
                origin=item.origin.value if hasattr(item.origin, "value") else str(item.origin),
            )
            session.add(r)
            new_reqs.append(r)

        # If status was analysed -> set to stale
        if eval_obj.status == EvaluationStatus.ANALYSED.value:
            eval_obj.status = EvaluationStatus.STALE.value

        eval_obj.updated_at = func.now()
        await session.commit()

        # Re-fetch
        return await EvaluationRepository.get_requirements(session, user_id, evaluation_id)

    @staticmethod
    async def get_latest_job(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> Optional[AnalysisJob]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None
        stmt = (
            select(AnalysisJob)
            .where(AnalysisJob.evaluation_id == evaluation_id)
            .order_by(desc(AnalysisJob.started_at), desc(AnalysisJob.created_at))
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def has_active_job(
        session: AsyncSession, evaluation_id: uuid.UUID
    ) -> bool:
        stmt = (
            select(func.count(AnalysisJob.id))
            .where(
                AnalysisJob.evaluation_id == evaluation_id,
                AnalysisJob.status.in_(["queued", "extracting", "analysing"]),
            )
        )
        res = await session.execute(stmt)
        count = res.scalar() or 0
        return count > 0

    @staticmethod
    async def create_job(
        session: AsyncSession,
        evaluation_id: uuid.UUID,
        kind: str,
        step_label: str = "",
    ) -> AnalysisJob:
        job = AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            kind=kind,
            status="queued",
            step_label=step_label,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    @staticmethod
    async def get_results_data(
        session: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, evaluation_id)
        if not eval_obj:
            return None

        # Fetch vendors
        v_stmt = select(Vendor).where(Vendor.evaluation_id == evaluation_id).order_by(Vendor.position)
        v_res = await session.execute(v_stmt)
        vendors = list(v_res.scalars().all())

        # Fetch findings
        f_stmt = select(Finding).where(Finding.evaluation_id == evaluation_id)
        f_res = await session.execute(f_stmt)
        findings = list(f_res.scalars().all())

        # Fetch costs
        c_stmt = select(CostBreakdown).where(CostBreakdown.evaluation_id == evaluation_id)
        c_res = await session.execute(c_stmt)
        costs = list(c_res.scalars().all())

        # Fetch clarifications
        cl_stmt = select(Clarification).where(Clarification.evaluation_id == evaluation_id)
        cl_res = await session.execute(cl_stmt)
        clarifications = list(cl_res.scalars().all())

        # Fetch criterion scores
        cs_stmt = select(CriterionScore).where(CriterionScore.evaluation_id == evaluation_id)
        cs_res = await session.execute(cs_stmt)
        criterion_scores = list(cs_res.scalars().all())

        # Fetch documents (for document filename lookup in evidence)
        d_stmt = select(Document).where(Document.evaluation_id == evaluation_id)
        d_res = await session.execute(d_stmt)
        docs_map = {doc.id: doc.filename for doc in d_res.scalars().all()}

        return {
            "evaluation": eval_obj,
            "vendors": vendors,
            "findings": findings,
            "costs": costs,
            "clarifications": clarifications,
            "criterion_scores": criterion_scores,
            "docs_map": docs_map,
        }
