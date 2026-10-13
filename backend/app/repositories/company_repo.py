from typing import List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company, Location
from app.models.evaluation import Evaluation
from app.models.user import User


class CompanyRepository:
    @staticmethod
    async def get_or_create_for_user(
        session: AsyncSession, user: User
    ) -> Company:
        if user.company_id is not None:
            stmt = select(Company).where(Company.id == user.company_id)
            res = await session.execute(stmt)
            company = res.scalar_one_or_none()
            if company is not None:
                return company

        new_cid = user.company_id or uuid.uuid4()
        await session.execute(
            insert(Company)
            .values(id=new_cid, name=None)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        if user.company_id != new_cid:
            user.company_id = new_cid
        await session.commit()
        stmt = select(Company).where(Company.id == new_cid)
        res = await session.execute(stmt)
        return res.scalar_one()

    @staticmethod
    async def list_locations_with_counts(
        session: AsyncSession, company_id: uuid.UUID
    ) -> List[Tuple[Location, int]]:
        stmt = (
            select(Location, func.count(Evaluation.id).label("evaluation_count"))
            .outerjoin(Evaluation, Evaluation.location_id == Location.id)
            .where(Location.company_id == company_id)
            .group_by(Location.id)
            .order_by(Location.position, Location.id)
        )
        res = await session.execute(stmt)
        return [(row[0], int(row[1] or 0)) for row in res.all()]

    @staticmethod
    async def get_location(
        session: AsyncSession, company_id: uuid.UUID, location_id: uuid.UUID
    ) -> Optional[Location]:
        stmt = select(Location).where(
            Location.id == location_id,
            Location.company_id == company_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_location_with_count(
        session: AsyncSession, company_id: uuid.UUID, location_id: uuid.UUID
    ) -> Optional[Tuple[Location, int]]:
        stmt = (
            select(Location, func.count(Evaluation.id).label("evaluation_count"))
            .outerjoin(Evaluation, Evaluation.location_id == Location.id)
            .where(
                Location.id == location_id,
                Location.company_id == company_id,
            )
            .group_by(Location.id)
        )
        res = await session.execute(stmt)
        row = res.first()
        if not row:
            return None
        return row[0], int(row[1] or 0)

    @staticmethod
    async def update_company_name(
        session: AsyncSession, company: Company, name: Optional[str]
    ) -> Company:
        company.name = name
        company.updated_at = func.now()
        await session.commit()
        await session.refresh(company)
        return company

    @staticmethod
    async def add_location(
        session: AsyncSession,
        company_id: uuid.UUID,
        name: str,
        city: str,
    ) -> Location:
        existing_stmt = (
            select(Location)
            .where(Location.company_id == company_id)
            .order_by(Location.position, Location.id)
        )
        existing = list((await session.execute(existing_stmt)).scalars().all())
        if any(loc.name.strip().lower() == name.lower() for loc in existing):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Location '{name}' already exists.",
            )

        next_pos = len(existing)
        loc = Location(
            id=uuid.uuid4(),
            company_id=company_id,
            name=name,
            city=city,
            position=next_pos,
        )
        session.add(loc)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Location '{name}' already exists.",
            )
        await session.refresh(loc)
        return loc

    @staticmethod
    async def update_location(
        session: AsyncSession,
        company_id: uuid.UUID,
        location: Location,
        name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Tuple[Location, int]:
        if name is not None:
            existing_stmt = select(Location).where(
                Location.company_id == company_id,
                Location.id != location.id,
            )
            existing = list((await session.execute(existing_stmt)).scalars().all())
            if any(loc.name.strip().lower() == name.lower() for loc in existing):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Location '{name}' already exists.",
                )
            location.name = name

        if city is not None:
            location.city = city

        location.updated_at = func.now()
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Location '{name}' already exists.",
            )

        res = await CompanyRepository.get_location_with_count(
            session, company_id, location.id
        )
        return res  # type: ignore[return-value]

    @staticmethod
    async def count_evaluations_using_location(
        session: AsyncSession, location_id: uuid.UUID
    ) -> int:
        stmt = select(func.count(Evaluation.id)).where(
            Evaluation.location_id == location_id
        )
        res = await session.execute(stmt)
        return int(res.scalar() or 0)

    @staticmethod
    async def delete_location(
        session: AsyncSession,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> None:
        await session.execute(
            delete(Location).where(
                Location.id == location_id,
                Location.company_id == company_id,
            )
        )

        rem_stmt = (
            select(Location)
            .where(
                Location.company_id == company_id,
                Location.id != location_id,
            )
            .order_by(Location.position, Location.id)
        )
        remaining = list((await session.execute(rem_stmt)).scalars().all())
        for new_pos, loc in enumerate(remaining):
            loc.position = new_pos

        await session.commit()
        session.expire_all()
