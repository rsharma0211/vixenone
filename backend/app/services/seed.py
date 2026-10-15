import logging
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, init_firebase
from app.core.config import settings
from app.core.database import async_session
from app.models.company import Company
from app.models.evaluation import Evaluation
from app.models.user import User
from app.schemas.user import UserProfileUpdate, UserRole
from app.services.seed_demo import DEMO_EMAIL, seed_demo_data
from app.services.storage import StorageService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

DEMO_PASSWORD = "demo1234"
DEMO_DISPLAY_NAME = "Priya Sharma"


async def run_seed(
    session: AsyncSession | None = None,
    auth_admin: Any | None = None,
    storage: StorageService | None = None,
    dataset_dir: Path | None = None,
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

        # Reconcile user rows for DEMO_EMAIL strictly according to the rule:
        # - only rows with the demo email are ever touched;
        # - a demo-email row is deleted only if it owns no evaluations;
        # - otherwise it is updated to the current Firebase id;
        # - rows with any other email are never touched.
        stmt_by_email = select(User).where(User.email == DEMO_EMAIL).order_by(User.created_at)
        res_email = await session.execute(stmt_by_email)
        demo_users = list(res_email.scalars().all())

        if demo_users:
            demo_users_with_evals: list[User] = []
            demo_users_without_evals: list[User] = []
            for u in demo_users:
                eval_count_stmt = select(func.count(Evaluation.id)).where(Evaluation.user_id == u.id)
                count = (await session.execute(eval_count_stmt)).scalar_one()
                if count > 0:
                    demo_users_with_evals.append(u)
                else:
                    demo_users_without_evals.append(u)

            if demo_users_with_evals:
                user = next((u for u in demo_users_with_evals if u.firebase_uid == user_record.uid), None) or demo_users_with_evals[0]
            else:
                user = next((u for u in demo_users_without_evals if u.firebase_uid == user_record.uid), None) or demo_users_without_evals[0]

            rows_to_delete = [u for u in demo_users_without_evals if u.id != user.id]
            extra_company_ids = [
                u.company_id for u in rows_to_delete if u.company_id and u.company_id != user.company_id
            ]
            for extra in rows_to_delete:
                await session.delete(extra)
            await session.flush()

            user.firebase_uid = user_record.uid
            user.display_name = DEMO_DISPLAY_NAME
            user.role = UserRole.FACILITIES_MANAGER
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
        await seed_demo_data(session, storage=storage, dataset_dir=dataset_dir)

        return user
    finally:
        if close_session:
            await session.close()
