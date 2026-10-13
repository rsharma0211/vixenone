from abc import ABC, abstractmethod
import os
from pathlib import Path
from typing import Optional
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


class CloudStorageService(StorageService):
    def __init__(self, bucket_name: str, client: Optional[object] = None):
        if not bucket_name or not str(bucket_name).strip():
            raise ValueError("Bucket name is required for Cloud Storage")
        self.bucket_name = str(bucket_name).strip()
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from google.cloud import storage as gcs
            # Credentials via ADC (no key files)
            self._client = gcs.Client()
        return self._client

    @property
    def bucket(self):
        return self.client.bucket(self.bucket_name)

    def _clean_path(self, path: str) -> str:
        return path.lstrip("/")

    def _sync_save(self, path: str, content: bytes) -> str:
        clean_path = self._clean_path(path)
        blob = self.bucket.blob(clean_path)
        # Objects stay private (default GCS behavior; do not call make_public)
        blob.upload_from_string(content)
        return clean_path

    def _sync_read(self, path: str) -> bytes:
        clean_path = self._clean_path(path)
        blob = self.bucket.blob(clean_path)
        try:
            if not blob.exists():
                raise FileNotFoundError(f"File not found: {path}")
            return blob.download_as_bytes()
        except Exception as exc:
            # Handle google.cloud.exceptions.NotFound or existing FileNotFoundError
            if exc.__class__.__name__ == "NotFound" or isinstance(exc, FileNotFoundError):
                raise FileNotFoundError(f"File not found: {path}") from exc
            raise

    def _sync_delete(self, path: str) -> bool:
        clean_path = self._clean_path(path)
        blob = self.bucket.blob(clean_path)
        try:
            if not blob.exists():
                return False
            blob.delete()
            return True
        except Exception as exc:
            if exc.__class__.__name__ == "NotFound":
                return False
            raise

    def _sync_exists(self, path: str) -> bool:
        clean_path = self._clean_path(path)
        blob = self.bucket.blob(clean_path)
        return bool(blob.exists())

    async def save(self, path: str, content: bytes) -> str:
        import asyncio
        return await asyncio.to_thread(self._sync_save, path, content)

    async def read(self, path: str) -> bytes:
        import asyncio
        return await asyncio.to_thread(self._sync_read, path)

    async def delete(self, path: str) -> bool:
        import asyncio
        return await asyncio.to_thread(self._sync_delete, path)

    async def exists(self, path: str) -> bool:
        import asyncio
        return await asyncio.to_thread(self._sync_exists, path)


def get_storage() -> StorageService:
    backend = settings.STORAGE_BACKEND.strip().lower()
    if backend == "local":
        return LocalStorageService(base_dir=settings.UPLOAD_DIR)
    elif backend in ("cloud", "gcs"):
        bucket_name = settings.storage_bucket
        if not bucket_name:
            raise ValueError("STORAGE_BUCKET_NAME environment variable is required when STORAGE_BACKEND is cloud")
        return CloudStorageService(bucket_name=bucket_name)
    raise ValueError(f"Unsupported storage backend: {settings.STORAGE_BACKEND}")
