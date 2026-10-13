import pytest
from sqlalchemy import select

from app.core.database import async_session
from app.models.user import User
from app.schemas.user import UserRole
from app.services.seed import run_seed
from app.services.seed_demo import DEMO_EMAIL


class FakeUserNotFoundError(Exception):
    pass


class FakeUserRecord:
    def __init__(self, uid: str, email: str, display_name: str):
        self.uid = uid
        self.email = email
        self.display_name = display_name


class FakeAuthAdmin:
    def __init__(self):
        self.users_by_email = {}
        self.create_user_calls = 0

    def get_user_by_email(self, email: str):
        if email not in self.users_by_email:
            raise FakeUserNotFoundError(f"User {email} not found")
        return self.users_by_email[email]

    def create_user(self, email: str, password: str, display_name: str):
        self.create_user_calls += 1
        uid = f"firebase-uid-{email.split('@')[0]}"
        rec = FakeUserRecord(uid=uid, email=email, display_name=display_name)
        self.users_by_email[email] = rec
        return rec


@pytest.mark.asyncio
async def test_seed_with_fake_admin_client():
    fake_admin = FakeAuthAdmin()

    async with async_session() as session:
        # 1. First run: creates the user when missing
        user1 = await run_seed(session=session, auth_admin=fake_admin)
        assert fake_admin.create_user_calls == 1
        assert DEMO_EMAIL in fake_admin.users_by_email
        expected_uid = fake_admin.users_by_email[DEMO_EMAIL].uid

        # The profile row id equals the Firebase user id
        assert user1.firebase_uid == expected_uid
        assert user1.email == DEMO_EMAIL
        assert user1.display_name == "Priya Sharma"
        assert user1.role == UserRole.FACILITIES_MANAGER

        # Verify DB state
        stmt = select(User).where(User.email == DEMO_EMAIL)
        res = await session.execute(stmt)
        users = res.scalars().all()
        assert len(users) == 1
        assert users[0].firebase_uid == expected_uid

        # 2. Reuses it when present & second run makes no changes
        user2 = await run_seed(session=session, auth_admin=fake_admin)
        # Did not create another user in Firebase
        assert fake_admin.create_user_calls == 1

        # Profile row id still equals Firebase user id
        assert user2.firebase_uid == expected_uid
        assert user2.id == user1.id

        # Verify DB still has exactly 1 row
        stmt2 = select(User).where(User.email == DEMO_EMAIL)
        res2 = await session.execute(stmt2)
        users2 = res2.scalars().all()
        assert len(users2) == 1
        assert users2[0].id == user1.id
        assert users2[0].firebase_uid == expected_uid


@pytest.mark.asyncio
async def test_seed_updates_existing_profile_with_older_firebase_id():
    fake_admin = FakeAuthAdmin()
    # Simulate a new/real Firebase UID
    new_firebase_uid = "real-firebase-uid-prod-9999"
    fake_admin.users_by_email[DEMO_EMAIL] = FakeUserRecord(
        uid=new_firebase_uid,
        email=DEMO_EMAIL,
        display_name="Priya Sharma",
    )

    async with async_session() as session:
        # Pre-seed or ensure an existing profile exists with an older Firebase ID
        stmt = select(User).where(User.email == DEMO_EMAIL)
        res = await session.execute(stmt)
        existing_user = res.scalars().first()

        old_firebase_id = "old-emulator-uid-0001"
        if existing_user is None:
            from app.models.company import Company
            comp = Company(name="Existing Northbridge Corp")
            session.add(comp)
            await session.flush()
            existing_user = User(
                firebase_uid=old_firebase_id,
                email=DEMO_EMAIL,
                display_name="Old Priya",
                company_id=comp.id,
                role=UserRole.FACILITIES_MANAGER,
            )
            session.add(existing_user)
            await session.commit()
            await session.refresh(existing_user)
        else:
            existing_user.firebase_uid = old_firebase_id
            await session.commit()
            await session.refresh(existing_user)

        user_id_before = existing_user.id
        company_id_before = existing_user.company_id

        # Verify company exists before seed run
        from app.models.company import Company
        stmt_comp = select(Company).where(Company.id == company_id_before)
        res_comp = await session.execute(stmt_comp)
        assert res_comp.scalar_one_or_none() is not None

        # Run seed with the real Firebase UID
        updated_user = await run_seed(session=session, auth_admin=fake_admin)

        # 1. Profile updated to new Firebase ID, same primary key and company
        assert updated_user.firebase_uid == new_firebase_uid
        assert updated_user.id == user_id_before
        assert updated_user.company_id == company_id_before

        # 2. Exactly 1 user row exists for demo email
        stmt_users = select(User).where(User.email == DEMO_EMAIL)
        res_users = await session.execute(stmt_users)
        all_demo_users = list(res_users.scalars().all())
        assert len(all_demo_users) == 1
        assert all_demo_users[0].firebase_uid == new_firebase_uid
        assert all_demo_users[0].id == user_id_before

        # 3. Exactly 1 company linked to user, no second company created
        stmt_linked_companies = select(Company).where(Company.id == updated_user.company_id)
        res_linked_companies = await session.execute(stmt_linked_companies)
        assert len(list(res_linked_companies.scalars().all())) == 1

