import asyncio
from collections.abc import Sequence
import subprocess
import sys

from app.services.seed import run_seed


def run_prepare(mode: str = "seed") -> int:
    """Run prepare tasks based on mode.

    Modes:
      - 'migrate': Runs alembic migrations only.
      - 'seed': Runs alembic migrations followed by demo seed.
    """
    normalized_mode = mode.strip().lower()
    if normalized_mode not in ("migrate", "seed"):
        print(
            f"Invalid prepare mode: '{mode}'. Must be 'migrate' or 'seed'.",
            file=sys.stderr,
        )
        return 1

    print(f"Preparing application environment (mode: {normalized_mode})...")
    print("1. Running database migrations (alembic upgrade head)...")
    res = subprocess.run(["alembic", "upgrade", "head"], check=False)
    if res.returncode != 0:
        print("Database migrations failed!", file=sys.stderr)
        return res.returncode

    if normalized_mode == "seed":
        print("2. Running demo seed via Firebase Admin SDK...")
        try:
            user = asyncio.run(run_seed())
            print(
                f"Seed completed successfully for user: {user.email} (UID: {user.firebase_uid})"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Demo seed failed: {exc}", file=sys.stderr)
            return 1

    print("Preparation completed successfully.")
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    mode = "seed"
    for arg in argv:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            mode = arg

    code = run_prepare(mode)
    if code != 0:
        sys.exit(code)


if __name__ == "__main__":
    main()
