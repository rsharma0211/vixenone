from pathlib import Path

from app.core.startup import get_startup_config


def test_production_mode_has_no_reload_and_no_migration():
    # Production mode: no reload, no migration, 1 worker, custom port
    cfg = get_startup_config(env="production", port=9000)
    assert cfg["is_production"] is True
    assert cfg["run_migrations"] is False
    assert cfg["reload"] is False
    assert cfg["workers"] == 1
    assert cfg["port"] == 9000
    assert "--reload" not in cfg["command"]
    assert "alembic" not in cfg["command"]
    assert "--workers" in cfg["command"]
    assert cfg["command"][cfg["command"].index("--workers") + 1] == "1"
    assert "--port" in cfg["command"]
    assert cfg["command"][cfg["command"].index("--port") + 1] == "9000"


def test_production_mode_port_fallback():
    # Production mode without port falls back to 8000
    cfg = get_startup_config(env="production", port=None)
    assert cfg["is_production"] is True
    assert cfg["run_migrations"] is False
    assert cfg["reload"] is False
    assert cfg["port"] == 8000
    assert "--reload" not in cfg["command"]
    assert "--port" in cfg["command"]
    assert cfg["command"][cfg["command"].index("--port") + 1] == "8000"


def test_development_mode_has_migrations_and_reload():
    # Development mode: migrations on start, auto-reload, port 8000
    cfg = get_startup_config(env="development", port=9000)
    assert cfg["is_production"] is False
    assert cfg["run_migrations"] is True
    assert cfg["reload"] is True
    assert cfg["port"] == 8000
    assert "--reload" in cfg["command"]


def test_entrypoint_script_logic_structure():
    # Inspect entrypoint.sh directly to assert on the start logic
    entrypoint_path = Path("/app/entrypoint.sh")
    if not entrypoint_path.exists():
        # Fallback for local workspace runs
        entrypoint_path = Path(__file__).parent.parent.parent / "entrypoint.sh"

    content = entrypoint_path.read_text()

    # Prepare command check
    assert 'if [ "$1" = "prepare" ]' in content
    assert "python -m app.cli.prepare" in content

    # Production branch: no migrations, no reload, single worker
    prod_block = content.split('if [ "$ENV_LOWER" = "production" ]')[1].split("else")[0]
    assert "alembic" not in prod_block
    assert "--reload" not in prod_block
    assert "--workers 1" in prod_block
    assert 'PORT="${PORT:-8000}"' in prod_block

    # Development branch (else block): runs alembic and reload
    dev_block = content.split("else")[1]
    assert "alembic upgrade head" in dev_block
    assert "--reload" in dev_block
