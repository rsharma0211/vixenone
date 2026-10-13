import configparser
from unittest.mock import patch

from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


def test_app_accepts_percent_encoded_database_url():
    # App Settings, make_url, and async engine factory accept percent-encoded passwords
    encoded_url = "postgresql+psycopg://vixenone:p%3B%3E%28word@localhost:5432/vixenone"
    s = Settings(DATABASE_URL=encoded_url)
    assert s.DATABASE_URL == encoded_url

    parsed = make_url(s.DATABASE_URL)
    assert parsed.username == "vixenone"
    assert parsed.password == "p;>(word"

    engine = create_async_engine(s.DATABASE_URL)
    assert engine is not None
    assert str(engine.url.render_as_string(hide_password=False)) == encoded_url


def test_migration_config_does_not_treat_percent_as_template_character():
    encoded_url = "postgresql+psycopg://vixenone:p%3B%3E%28word@localhost:5432/vixenone"
    cfg = Config("alembic.ini")

    # The migration config must not treat % as a template character
    # Ensure file_config interpolation is set to non-interpolating Interpolation
    cfg.file_config._interpolation = configparser.Interpolation()

    # Must not raise ValueError: invalid interpolation syntax
    cfg.set_main_option("sqlalchemy.url", encoded_url)
    retrieved = cfg.get_main_option("sqlalchemy.url")
    assert retrieved == encoded_url

    # Check section retrieval
    sec = cfg.get_section(cfg.config_ini_section, {})
    assert sec.get("sqlalchemy.url") == encoded_url


def test_alembic_env_loads_with_percent_encoded_database_url():
    encoded_url = "postgresql+psycopg://vixenone:p%3B%3E%28word@localhost:5432/vixenone"
    cfg = Config("alembic.ini")

    with patch("app.core.config.settings.DATABASE_URL", encoded_url):
        from alembic import command
        # Offline upgrade generates SQL without crashing on % interpolation
        command.upgrade(cfg, "head", sql=True)
