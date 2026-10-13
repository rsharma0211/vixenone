from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.cli.prepare import main, run_prepare


def test_prepare_mode_migrate_success():
    with patch("subprocess.run") as mock_subproc, patch(
        "app.cli.prepare.run_seed", new_callable=AsyncMock
    ) as mock_seed:
        mock_subproc.return_value = MagicMock(returncode=0)

        ret = run_prepare("migrate")
        assert ret == 0

        # Subprocess ran alembic upgrade head
        mock_subproc.assert_called_once_with(["alembic", "upgrade", "head"], check=False)
        # Seed was NOT called
        mock_seed.assert_not_called()


def test_prepare_mode_seed_success():
    with patch("subprocess.run") as mock_subproc, patch(
        "app.cli.prepare.run_seed", new_callable=AsyncMock
    ) as mock_seed:
        mock_subproc.return_value = MagicMock(returncode=0)
        fake_user = MagicMock()
        fake_user.email = "demo@vixenone.app"
        fake_user.firebase_uid = "uid-123"
        mock_seed.return_value = fake_user

        ret = run_prepare("seed")
        assert ret == 0

        # Subprocess ran alembic upgrade head
        mock_subproc.assert_called_once_with(["alembic", "upgrade", "head"], check=False)
        # Seed WAS called
        mock_seed.assert_called_once()


def test_prepare_default_mode_is_seed():
    with patch("subprocess.run") as mock_subproc, patch(
        "app.cli.prepare.run_seed", new_callable=AsyncMock
    ) as mock_seed:
        mock_subproc.return_value = MagicMock(returncode=0)
        fake_user = MagicMock()
        fake_user.email = "demo@vixenone.app"
        fake_user.firebase_uid = "uid-123"
        mock_seed.return_value = fake_user

        # Default argument
        ret = run_prepare()
        assert ret == 0

        mock_subproc.assert_called_once_with(["alembic", "upgrade", "head"], check=False)
        mock_seed.assert_called_once()


def test_prepare_invalid_mode():
    with patch("subprocess.run") as mock_subproc, patch(
        "app.cli.prepare.run_seed", new_callable=AsyncMock
    ) as mock_seed:
        ret = run_prepare("unknown_mode")
        assert ret == 1
        mock_subproc.assert_not_called()
        mock_seed.assert_not_called()


def test_prepare_migration_failure():
    with patch("subprocess.run") as mock_subproc, patch(
        "app.cli.prepare.run_seed", new_callable=AsyncMock
    ) as mock_seed:
        mock_subproc.return_value = MagicMock(returncode=2)

        ret = run_prepare("migrate")
        assert ret == 2
        mock_seed.assert_not_called()


def test_prepare_seed_failure():
    with patch("subprocess.run") as mock_subproc, patch(
        "app.cli.prepare.run_seed", new_callable=AsyncMock
    ) as mock_seed:
        mock_subproc.return_value = MagicMock(returncode=0)
        mock_seed.side_effect = RuntimeError("Firebase error")

        ret = run_prepare("seed")
        assert ret == 1


def test_main_cli_arguments():
    with patch("app.cli.prepare.run_prepare") as mock_run:
        mock_run.return_value = 0

        # Positional
        main(["migrate"])
        mock_run.assert_called_with("migrate")

        # Flag format
        main(["--mode=migrate"])
        mock_run.assert_called_with("migrate")

        # Empty args defaults to seed
        main([])
        mock_run.assert_called_with("seed")


def test_main_cli_exit_on_error():
    with patch("app.cli.prepare.run_prepare") as mock_run:
        mock_run.return_value = 1
        with pytest.raises(SystemExit) as exc:
            main(["migrate"])
        assert exc.value.code == 1
