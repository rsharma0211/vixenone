import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.company_repo import CompanyRepository
from app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
    LocationCreate,
    LocationResponse,
    LocationUpdate,
)


class CompanyService:
    @staticmethod
    async def get_company(
        session: AsyncSession, user: User
    ) -> CompanyResponse:
        company = await CompanyRepository.get_or_create_for_user(session, user)
        locs_with_counts = await CompanyRepository.list_locations_with_counts(
            session, company.id
        )
        return CompanyResponse(
            id=company.id,
            name=company.name,
            locations=[
                LocationResponse(
                    id=loc.id,
                    name=loc.name,
                    city=loc.city,
                    position=loc.position,
                    evaluation_count=count,
                )
                for loc, count in locs_with_counts
            ],
        )

    @staticmethod
    async def update_company(
        session: AsyncSession, user: User, payload: CompanyUpdate
    ) -> CompanyResponse:
        company = await CompanyRepository.get_or_create_for_user(session, user)
        await CompanyRepository.update_company_name(session, company, payload.name)
        return await CompanyService.get_company(session, user)

    @staticmethod
    async def add_location(
        session: AsyncSession, user: User, payload: LocationCreate
    ) -> LocationResponse:
        company = await CompanyRepository.get_or_create_for_user(session, user)
        loc = await CompanyRepository.add_location(
            session, company.id, payload.name, payload.city
        )
        return LocationResponse(
            id=loc.id,
            name=loc.name,
            city=loc.city,
            position=loc.position,
            evaluation_count=0,
        )

    @staticmethod
    async def update_location(
        session: AsyncSession,
        user: User,
        location_id: uuid.UUID,
        payload: LocationUpdate,
    ) -> LocationResponse:
        company = await CompanyRepository.get_or_create_for_user(session, user)
        loc = await CompanyRepository.get_location(session, company.id, location_id)
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {location_id} not found",
            )
        updated_loc, count = await CompanyRepository.update_location(
            session,
            company.id,
            loc,
            name=payload.name,
            city=payload.city,
        )
        return LocationResponse(
            id=updated_loc.id,
            name=updated_loc.name,
            city=updated_loc.city,
            position=updated_loc.position,
            evaluation_count=count,
        )

    @staticmethod
    async def delete_location(
        session: AsyncSession,
        user: User,
        location_id: uuid.UUID,
    ) -> None:
        company = await CompanyRepository.get_or_create_for_user(session, user)
        loc = await CompanyRepository.get_location(session, company.id, location_id)
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {location_id} not found",
            )
        count = await CompanyRepository.count_evaluations_using_location(
            session, location_id
        )
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Used by {count} evaluations.",
            )
        await CompanyRepository.delete_location(session, company.id, location_id)
