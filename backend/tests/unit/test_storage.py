import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings
from app.services.storage import CloudStorageService, LocalStorageService, get_storage

TEST_DIR = Path("/tmp/vixenone_test_uploads")


@pytest.fixture(autouse=True)
def cleanup():
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    yield
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)


class FakeNotFound(Exception):
    pass


class FakeBlob:
    def __init__(self, name: str, bucket: "FakeBucket"):
        self.name = name
        self.bucket = bucket

    def upload_from_string(self, data: bytes):
        self.bucket.objects[self.name] = data

    def download_as_bytes(self) -> bytes:
        if self.name not in self.bucket.objects:
            raise FakeNotFound(f"Object {self.name} not found")
        return self.bucket.objects[self.name]

    def delete(self):
        if self.name not in self.bucket.objects:
            raise FakeNotFound(f"Object {self.name} not found")
        del self.bucket.objects[self.name]

    def exists(self) -> bool:
        return self.name in self.bucket.objects


class FakeBucket:
    def __init__(self, name: str):
        self.name = name
        self.objects = {}

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(name, self)


class FakeStorageClient:
    def __init__(self):
        self.buckets = {}

    def bucket(self, name: str) -> FakeBucket:
        if name not in self.buckets:
            self.buckets[name] = FakeBucket(name)
        return self.buckets[name]


@pytest.mark.asyncio
async def test_storage_lifecycle():
    storage = LocalStorageService(base_dir=str(TEST_DIR))
    filename = "proposals/test_doc.txt"
    content = b"Housekeeping Proposal Content 2026"

    # Initially does not exist
    assert await storage.exists(filename) is False

    # Save
    saved_path = await storage.save(filename, content)
    assert saved_path == filename
    assert await storage.exists(filename) is True

    # Read
    read_content = await storage.read(filename)
    assert read_content == content

    # Delete
    deleted = await storage.delete(filename)
    assert deleted is True
    assert await storage.exists(filename) is False

    # Second delete returns False
    deleted_again = await storage.delete(filename)
    assert deleted_again is False


@pytest.mark.asyncio
async def test_storage_path_traversal():
    storage = LocalStorageService(base_dir=str(TEST_DIR))
    with pytest.raises(ValueError, match="Path traversal detected"):
        await storage.save("../../etc/passwd", b"bad")


@pytest.mark.asyncio
async def test_cloud_storage_lifecycle_with_fake_client():
    fake_client = FakeStorageClient()
    storage = CloudStorageService(bucket_name="vixenone-proposals-bucket", client=fake_client)
    filename = "evaluations/demo_eval/rfp.pdf"
    content = b"%PDF-1.4 mock content for RFP evaluation"

    # Initially does not exist
    assert await storage.exists(filename) is False

    # Save
    saved_path = await storage.save(filename, content)
    assert saved_path == filename
    assert await storage.exists(filename) is True

    # Read
    read_content = await storage.read(filename)
    assert read_content == content

    # Delete
    deleted = await storage.delete(filename)
    assert deleted is True
    assert await storage.exists(filename) is False

    # Second delete returns False
    deleted_again = await storage.delete(filename)
    assert deleted_again is False


@pytest.mark.asyncio
async def test_cloud_storage_missing_object_behavior():
    fake_client = FakeStorageClient()
    storage = CloudStorageService(bucket_name="vixenone-proposals-bucket", client=fake_client)
    filename = "missing/file.docx"

    assert await storage.exists(filename) is False

    with pytest.raises(FileNotFoundError, match=f"File not found: {filename}"):
        await storage.read(filename)

    deleted = await storage.delete(filename)
    assert deleted is False


def test_storage_factory_selection():
    # Local backend
    with patch("app.services.storage.settings.STORAGE_BACKEND", "local"):
        svc = get_storage()
        assert isinstance(svc, LocalStorageService)

    # Cloud backend with bucket
    with patch("app.services.storage.settings.STORAGE_BACKEND", "cloud"), \
         patch("app.services.storage.settings.STORAGE_BUCKET_NAME", "my-gcs-bucket"):
        svc = get_storage()
        assert isinstance(svc, CloudStorageService)
        assert svc.bucket_name == "my-gcs-bucket"

    # Cloud backend missing bucket name raises ValueError
    with patch("app.services.storage.settings.STORAGE_BACKEND", "cloud"), \
         patch("app.services.storage.settings.STORAGE_BUCKET_NAME", None), \
         patch("app.services.storage.settings.GCS_BUCKET_NAME", None):
        with pytest.raises(ValueError, match="STORAGE_BUCKET_NAME"):
            get_storage()

    # Unknown backend raises ValueError
    with patch("app.services.storage.settings.STORAGE_BACKEND", "aws_s3"):
        with pytest.raises(ValueError, match="Unsupported storage backend: aws_s3"):
            get_storage()
