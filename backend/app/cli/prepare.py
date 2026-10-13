import asyncio
import subprocess
import sys

from app.services.seed import run_seed


def main():
    print("Preparing application environment...")
    print("1. Running database migrations (alembic upgrade head)...")
    res = subprocess.run(["alembic", "upgrade", "head"], check=False)
    if res.returncode != 0:
        print("Database migrations failed!", file=sys.stderr)
        sys.exit(res.returncode)

    print("2. Running demo seed via Firebase Admin SDK...")
    try:
        user = asyncio.run(run_seed())
        print(f"Seed completed successfully for user: {user.email} (UID: {user.firebase_uid})")
    except Exception as exc:  # noqa: BLE001
        print(f"Demo seed failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Preparation completed successfully.")


if __name__ == "__main__":
    main()
