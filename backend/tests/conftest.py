import asyncio
from pathlib import Path
import shutil
import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.database import async_session
from app.services.seed import run_seed


def check_safety_guard(database_url: str, upload_dir: str) -> None:
    """Safety guard: verify tests run only against an isolated test database and temporary storage."""
    try:
        url = make_url(database_url)
        db_name = url.database or ""
    except Exception as exc:
        raise RuntimeError(f"Safety guard: invalid DATABASE_URL '{database_url}': {exc}") from exc

    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Safety guard: refused to run tests because database name '{db_name}' does not end with '_test'. "
            "Tests must run against an isolated test database (e.g. vixenone_test)."
        )

    resolved_upload = Path(upload_dir).resolve()
    dev_paths = [Path("/app/uploads").resolve()]
    repo_uploads = (Path(__file__).resolve().parents[2] / "uploads").resolve()
    dev_paths.append(repo_uploads)

    for dev_path in dev_paths:
        if resolved_upload == dev_path or dev_path in resolved_upload.parents:
            raise RuntimeError(
                f"Safety guard: refused to run tests because storage path '{upload_dir}' points at the dev uploads folder. "
                "Tests must use an isolated temporary storage folder."
            )


def pytest_configure(config: pytest.Config) -> None:
    try:
        check_safety_guard(settings.DATABASE_URL, settings.UPLOAD_DIR)
    except Exception as exc:
        raise pytest.UsageError(str(exc)) from exc


@pytest.fixture(scope="session", autouse=True)
def test_storage():
    """Ensure temporary test storage directory exists during testing and is removed after the run."""
    storage_path = Path(settings.UPLOAD_DIR)
    if storage_path.exists():
        shutil.rmtree(storage_path, ignore_errors=True)
    storage_path.mkdir(parents=True, exist_ok=True)
    yield storage_path
    if storage_path.exists():
        shutil.rmtree(storage_path, ignore_errors=True)


class FakeUserRecord:
    def __init__(self, uid: str, email: str, display_name: str):
        self.uid = uid
        self.email = email
        self.display_name = display_name


class FakeUserNotFoundError(Exception):
    pass


class FakeAuthAdmin:
    def __init__(self):
        self.users_by_email: dict[str, FakeUserRecord] = {}

    def get_user_by_email(self, email: str):
        if email in self.users_by_email:
            return self.users_by_email[email]
        raise FakeUserNotFoundError(f"User {email} not found")

    def create_user(self, email: str, password: str, display_name: str):
        uid = "demo-uid-vixenone"
        rec = FakeUserRecord(uid=uid, email=email, display_name=display_name)
        self.users_by_email[email] = rec
        return rec


@pytest.fixture
def seed_demo(test_storage):
    """Seed demo data into the test database through the existing seed function."""
    async def _do_seed():
        async with async_session() as session:
            fake_admin = FakeAuthAdmin()
            user = await run_seed(session=session, auth_admin=fake_admin)
            return user

    return asyncio.run(_do_seed())
