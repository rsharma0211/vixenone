from abc import ABC, abstractmethod
import asyncio
from typing import Callable, Optional, Set
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.llm.client import GeminiClientFactory, create_gemini_client
from app.services.storage import StorageService, get_storage
from app.services.worker import run_job_by_id

SessionFactory = Callable[[], AsyncSession]
StorageFactory = Callable[[], StorageService]


class JobLauncher(ABC):
    """Interface for launching background jobs by ID."""

    @abstractmethod
    async def launch(self, job_id: uuid.UUID) -> None:
        """Start execution for the given job_id."""
        ...


class InProcessJobLauncher(JobLauncher):
    """In-process launcher that schedules run_job_by_id as an asyncio Task and retains a strong reference."""

    def __init__(
        self,
        session_factory: SessionFactory = async_session,
        gemini_client_factory: GeminiClientFactory = create_gemini_client,
        storage_factory: StorageFactory = get_storage,
    ) -> None:
        self._session_factory = session_factory
        self._gemini_client_factory = gemini_client_factory
        self._storage_factory = storage_factory
        self.active_tasks: Set[asyncio.Task[None]] = set()

    async def launch(self, job_id: uuid.UUID) -> None:
        task = asyncio.create_task(
            run_job_by_id(
                job_id=job_id,
                session_factory=self._session_factory,
                gemini_client_factory=self._gemini_client_factory,
                storage_factory=self._storage_factory,
            )
        )
        self.active_tasks.add(task)
        task.add_done_callback(self.active_tasks.discard)


class InlineJobLauncher(JobLauncher):
    """Test launcher that awaits the worker inline with provided factories."""

    def __init__(
        self,
        session_factory: SessionFactory,
        gemini_client_factory: GeminiClientFactory,
        storage_factory: Optional[StorageFactory] = None,
    ) -> None:
        self._session_factory = session_factory
        self._gemini_client_factory = gemini_client_factory
        self._storage_factory = storage_factory or get_storage

    async def launch(self, job_id: uuid.UUID) -> None:
        await run_job_by_id(
            job_id=job_id,
            session_factory=self._session_factory,
            gemini_client_factory=self._gemini_client_factory,
            storage_factory=self._storage_factory,
        )


_default_launcher = InProcessJobLauncher()


def get_job_launcher() -> JobLauncher:
    """FastAPI dependency returning the configured JobLauncher."""
    return _default_launcher
