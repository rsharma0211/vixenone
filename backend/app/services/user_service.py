from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserProfileUpdate, UserRole


class UserService:
    @staticmethod
    def _compute_fallback_display_name(auth_user: AuthenticatedUser) -> str:
        if auth_user.display_name and auth_user.display_name.strip():
            return auth_user.display_name.strip()
        email = auth_user.email or ""
        if "@" in email:
            fallback = email.split("@")[0].strip()
            if fallback:
                return fallback
        return email.strip() or "User"

    @classmethod
    async def get_or_create_profile(
        cls, session: AsyncSession, auth_user: AuthenticatedUser
    ) -> User:
        display_name = cls._compute_fallback_display_name(auth_user)
        email = auth_user.email or ""
        return await UserRepository.get_or_create(
            session=session,
            firebase_uid=auth_user.uid,
            email=email,
            display_name=display_name,
            default_role=UserRole.FACILITIES_MANAGER,
        )

    @classmethod
    async def update_profile(
        cls,
        session: AsyncSession,
        auth_user: AuthenticatedUser,
        update_data: UserProfileUpdate,
    ) -> User:
        # Ensure user exists before applying updates
        user = await cls.get_or_create_profile(session, auth_user)
        if update_data.display_name is not None or update_data.role is not None:
            updated_user = await UserRepository.update(
                session=session,
                firebase_uid=auth_user.uid,
                display_name=update_data.display_name,
                role=update_data.role,
            )
            if updated_user is not None:
                return updated_user
        return user
