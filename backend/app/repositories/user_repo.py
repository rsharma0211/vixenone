from typing import Optional
import uuid
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.company import Company
from app.models.user import User
from app.schemas.user import UserRole


class UserRepository:
    @staticmethod
    async def get_by_firebase_uid(
        session: AsyncSession, firebase_uid: str
    ) -> Optional[User]:
        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        firebase_uid: str,
        email: str,
        display_name: str,
        default_role: UserRole = UserRole.FACILITIES_MANAGER,
    ) -> User:
        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is not None:
            return user

        new_company_id = uuid.uuid4()
        await session.execute(
            insert(Company).values(id=new_company_id, name=None)
        )

        insert_stmt = (
            insert(User)
            .values(
                id=uuid.uuid4(),
                company_id=new_company_id,
                firebase_uid=firebase_uid,
                email=email,
                display_name=display_name,
                role=default_role,
            )
            .on_conflict_do_update(
                index_elements=["firebase_uid"],
                set_={"updated_at": func.now()},
            )
            .returning(User)
        )
        scalars_result = await session.scalars(insert_stmt)
        created_user = scalars_result.one()
        if created_user.company_id != new_company_id:
            await session.execute(
                delete(Company).where(Company.id == new_company_id)
            )
        await session.commit()
        return created_user

    @staticmethod
    async def update(
        session: AsyncSession,
        firebase_uid: str,
        display_name: Optional[str] = None,
        role: Optional[UserRole] = None,
    ) -> Optional[User]:
        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None

        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            user.role = role
        user.updated_at = func.now()

        await session.commit()
        await session.refresh(user)
        return user
