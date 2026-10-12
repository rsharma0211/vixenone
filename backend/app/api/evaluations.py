from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.repositories.evaluation_repo import EvaluationRepository
from app.schemas.evaluation import (
    AnalysisJobResponse,
    DocumentResponse,
    EvaluationCreate,
    EvaluationDetailResponse,
    EvaluationResultsResponse,
    EvaluationsListResponse,
    EvaluationUpdate,
    RequirementItem,
)
from app.services.evaluation_service import EvaluationService
from app.services.user_service import UserService

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("", response_model=EvaluationsListResponse)
async def list_evaluations(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationsListResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    data = await EvaluationService.get_summary_list(db, user.id)
    return EvaluationsListResponse.model_validate(data)


@router.post("", response_model=EvaluationDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    payload: EvaluationCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationDetailResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    eval_obj = await EvaluationRepository.create(
        db,
        user.id,
        title=payload.title,
        category=payload.category,
        vendor_names=payload.vendor_names,
    )
    return await EvaluationService.get_detail(db, user.id, eval_obj.id)


@router.get("/{id}", response_model=EvaluationDetailResponse)
async def get_evaluation(
    id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationDetailResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await EvaluationService.get_detail(db, user.id, id)


@router.patch("/{id}", response_model=EvaluationDetailResponse)
async def update_evaluation(
    id: uuid.UUID,
    payload: EvaluationUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationDetailResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    eval_obj = await EvaluationRepository.update(
        db,
        user.id,
        id,
        title=payload.title,
        category=payload.category,
        status=payload.status.value if payload.status else None,
    )
    if not eval_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation {id} not found",
        )
    return await EvaluationService.get_detail(db, user.id, id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    user = await UserService.get_or_create_profile(db, current_user)
    await EvaluationService.delete_evaluation(db, user.id, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/documents", response_model=DocumentResponse)
async def upload_document(
    id: uuid.UUID,
    file: UploadFile = File(...),
    kind: str = Form(...),
    vendor_id: Optional[uuid.UUID] = Form(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await EvaluationService.upload_document(
        db,
        user.id,
        id,
        file=file,
        kind=kind,
        vendor_id=vendor_id,
    )


@router.delete("/{id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    id: uuid.UUID,
    doc_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    user = await UserService.get_or_create_profile(db, current_user)
    await EvaluationService.delete_document(db, user.id, id, doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{id}/requirements", response_model=List[RequirementItem])
async def get_requirements(
    id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RequirementItem]:
    user = await UserService.get_or_create_profile(db, current_user)
    reqs = await EvaluationRepository.get_requirements(db, user.id, id)
    if reqs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation {id} not found",
        )
    return [RequirementItem.model_validate(r) for r in reqs]


@router.put("/{id}/requirements", response_model=List[RequirementItem])
async def replace_requirements(
    id: uuid.UUID,
    payload: List[RequirementItem],
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RequirementItem]:
    user = await UserService.get_or_create_profile(db, current_user)
    reqs = await EvaluationRepository.replace_requirements(db, user.id, id, payload)
    if reqs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation {id} not found",
        )
    return [RequirementItem.model_validate(r) for r in reqs]


@router.get("/{id}/jobs/latest", response_model=Optional[AnalysisJobResponse])
async def get_latest_job(
    id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[AnalysisJobResponse]:
    user = await UserService.get_or_create_profile(db, current_user)
    job = await EvaluationRepository.get_latest_job(db, user.id, id)
    if job is None:
        eval_obj = await EvaluationRepository.get_by_id(db, user.id, id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {id} not found",
            )
        return None
    return AnalysisJobResponse.model_validate(job)


@router.get("/{id}/results", response_model=EvaluationResultsResponse)
async def get_results(
    id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResultsResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await EvaluationService.get_results(db, user.id, id)
