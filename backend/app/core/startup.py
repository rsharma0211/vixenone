from typing import Any, Dict, Optional


def get_startup_config(env: Optional[str] = None, port: Optional[Any] = None) -> Dict[str, Any]:
    """Determine runtime startup parameters and commands based on environment mode.

    - Production: no migrations, no reload, single worker process (1), listen on Cloud Run port (fallback 8000).
    - Development: unchanged (migrations on start, auto-reload, port 8000).
    """
    resolved_env = (env or "development").strip().lower()
    is_prod = resolved_env in ("production", "prod")
    resolved_port = int(port) if port is not None and str(port).strip() else 8000

    if is_prod:
        return {
            "is_production": True,
            "run_migrations": False,
            "reload": False,
            "workers": 1,
            "port": resolved_port,
            "command": [
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(resolved_port),
                "--workers",
                "1",
            ],
        }

    return {
        "is_production": False,
        "run_migrations": True,
        "reload": True,
        "workers": 1,
        "port": 8000,
        "command": [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload",
        ],
    }
