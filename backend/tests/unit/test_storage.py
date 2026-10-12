import pytest
import shutil
from pathlib import Path

from app.services.storage import LocalStorageService

TEST_DIR = Path("/tmp/vixenone_test_uploads")


@pytest.fixture(autouse=True)
def cleanup():
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    yield
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)


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
