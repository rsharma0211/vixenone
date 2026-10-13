from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.repositories.criteria_repo import CriteriaRepository
from app.schemas.criteria import (
    EvaluationCriterionResponse,
    EvaluationCriterionUpdateItem,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/api/criteria", tags=["criteria"])


@router.get("", response_model=List[EvaluationCriterionResponse])
async def get_criteria(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[EvaluationCriterionResponse]:
    user = await UserService.get_or_create_profile(db, current_user)
    criteria = await CriteriaRepository.get_or_create_builtins(db, user.id)
    return [EvaluationCriterionResponse.model_validate(c) for c in criteria]


@router.put("", response_model=List[EvaluationCriterionResponse])
async def update_criteria(
    payload: List[EvaluationCriterionUpdateItem],
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[EvaluationCriterionResponse]:
    user = await UserService.get_or_create_profile(db, current_user)
    criteria = await CriteriaRepository.atomic_replace(db, user.id, payload)
    return [EvaluationCriterionResponse.model_validate(c) for c in criteria]
