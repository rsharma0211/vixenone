import pytest
from tests.conftest import check_safety_guard


def test_safety_guard_rejects_non_test_db():
    with pytest.raises(RuntimeError, match="does not end with '_test'"):
        check_safety_guard(
            "postgresql+psycopg://vixenone:vixenone@postgres:5432/vixenone",
            "/tmp/isolated_test_uploads",
        )


def test_safety_guard_rejects_dev_uploads_container_path():
    with pytest.raises(RuntimeError, match="points at the dev uploads folder"):
        check_safety_guard(
            "postgresql+psycopg://vixenone:vixenone@postgres:5432/vixenone_test",
            "/app/uploads",
        )


def test_safety_guard_rejects_dev_uploads_subpath():
    with pytest.raises(RuntimeError, match="points at the dev uploads folder"):
        check_safety_guard(
            "postgresql+psycopg://vixenone:vixenone@postgres:5432/vixenone_test",
            "/app/uploads/nested_folder",
        )


def test_safety_guard_rejects_invalid_db_url():
    with pytest.raises(RuntimeError, match="invalid DATABASE_URL"):
        check_safety_guard(
            "not-a-valid-database-url",
            "/tmp/isolated_test_uploads",
        )


def test_safety_guard_accepts_test_db_and_temp_storage():
    # Should not raise any error
    check_safety_guard(
        "postgresql+psycopg://vixenone:vixenone@postgres:5432/vixenone_test",
        "/tmp/isolated_test_uploads",
    )
