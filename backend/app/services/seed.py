import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, init_firebase
from app.core.config import settings
from app.core.database import async_session
from app.models.company import Company
from app.models.user import User
from app.schemas.user import UserProfileUpdate, UserRole
from app.services.seed_demo import DEMO_EMAIL, seed_demo_data
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

DEMO_PASSWORD = "demo1234"
DEMO_DISPLAY_NAME = "Priya Sharma"


async def run_seed(
    session: AsyncSession | None = None,
    auth_admin: Any | None = None,
) -> User:
    """Run idempotent seed:
    1. Look up demo@vixenone.app in Firebase; if missing, create it.
    2. Create or update profile row in Postgres keyed exactly as /api/me keys it (role facilities_manager).
    3. Run existing company, locations, criteria and demo-data seed for that user.
    """
    # 1. Firebase Admin lookup/create
    auth_client: Any
    if auth_admin is not None:
        auth_client = auth_admin
    else:
        init_firebase(settings)
        from firebase_admin import auth as fb_auth
        auth_client = fb_auth

    try:
        user_record = auth_client.get_user_by_email(DEMO_EMAIL)
        logger.info("Found existing Firebase user: %s (UID: %s)", DEMO_EMAIL, user_record.uid)
    except Exception as exc:
        is_not_found = (
            exc.__class__.__name__ in ("UserNotFoundError", "NotFoundError")
            or "not found" in str(exc).lower()
            or "no user record found" in str(exc).lower()
        )
        if is_not_found:
            user_record = auth_client.create_user(
                email=DEMO_EMAIL,
                password=DEMO_PASSWORD,
                display_name=DEMO_DISPLAY_NAME,
            )
            logger.info("Created new Firebase user: %s (UID: %s)", DEMO_EMAIL, user_record.uid)
        else:
            raise

    # 2. Database session and profile creation/update
    close_session = False
    if session is None:
        session = async_session()
        close_session = True

    try:
        auth_user = AuthenticatedUser(
            uid=user_record.uid,
            email=getattr(user_record, "email", None) or DEMO_EMAIL,
            display_name=getattr(user_record, "display_name", None) or DEMO_DISPLAY_NAME,
        )

        # Reconcile user rows for DEMO_EMAIL to ensure exactly one user with firebase_uid = user_record.uid
        stmt_by_email = select(User).where(User.email == DEMO_EMAIL).order_by(User.created_at)
        res_email = await session.execute(stmt_by_email)
        demo_users = list(res_email.scalars().all())

        if demo_users:
            user = demo_users[0]
            user.firebase_uid = user_record.uid
            user.display_name = DEMO_DISPLAY_NAME
            user.role = UserRole.FACILITIES_MANAGER
            extra_company_ids = [
                u.company_id for u in demo_users[1:] if u.company_id and u.company_id != user.company_id
            ]
            for extra in demo_users[1:]:
                await session.delete(extra)
            await session.flush()
            if extra_company_ids:
                await session.execute(delete(Company).where(Company.id.in_(extra_company_ids)))
            await session.commit()
            await session.refresh(user)
        else:
            # Keyed exactly as the /api/me endpoint keys it
            user = await UserService.get_or_create_profile(session, auth_user)
            user = await UserService.update_profile(
                session,
                auth_user,
                UserProfileUpdate(
                    display_name=DEMO_DISPLAY_NAME,
                    role=UserRole.FACILITIES_MANAGER,
                ),
            )

        # 3. Run company, locations, criteria and demo-data seed
        await seed_demo_data(session)

        return user
    finally:
        if close_session:
            await session.close()
