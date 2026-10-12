from abc import ABC, abstractmethod
import os
from pathlib import Path
import aiofiles
import aiofiles.os

from app.core.config import settings


class StorageService(ABC):
    @abstractmethod
    async def save(self, path: str, content: bytes) -> str:
        """Save content to the specified path and return the relative path/key."""
        pass

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read content from the specified path."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete content at the specified path. Return True if deleted, False if not found."""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists at the specified path."""
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        target = (self.base_dir / path.lstrip("/")).resolve()
        # Security: prevent path traversal attacks outside base_dir
        if not str(target).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Path traversal detected: {path}")
        return target

    async def save(self, path: str, content: bytes) -> str:
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target, "wb") as f:
            await f.write(content)
        return path.lstrip("/")

    async def read(self, path: str) -> bytes:
        target = self._resolve_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        async with aiofiles.open(target, "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> bool:
        target = self._resolve_path(path)
        if not target.is_file():
            return False
        await aiofiles.os.remove(target)
        return True

    async def exists(self, path: str) -> bool:
        target = self._resolve_path(path)
        return target.is_file()


def get_storage() -> StorageService:
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "local":
        return LocalStorageService(base_dir=settings.UPLOAD_DIR)
    raise ValueError(f"Unsupported storage backend: {settings.STORAGE_BACKEND}")
