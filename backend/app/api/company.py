import uuid
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
    LocationCreate,
    LocationResponse,
    LocationUpdate,
)
from app.services.company_service import CompanyService
from app.services.user_service import UserService

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("", response_model=CompanyResponse)
async def get_company(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await CompanyService.get_company(db, user)


@router.patch("", response_model=CompanyResponse)
async def update_company(
    payload: CompanyUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await CompanyService.update_company(db, user, payload)


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def add_location(
    payload: LocationCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await CompanyService.add_location(db, user, payload)


@router.patch("/locations/{id}", response_model=LocationResponse)
async def update_location(
    id: uuid.UUID,
    payload: LocationUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await CompanyService.update_location(db, user, id, payload)


@router.delete("/locations/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    user = await UserService.get_or_create_profile(db, current_user)
    await CompanyService.delete_location(db, user, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
