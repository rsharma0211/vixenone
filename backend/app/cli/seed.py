import asyncio
import sys

from app.services.seed import run_seed


def main():
    try:
        user = asyncio.run(run_seed())
        print(f"Seed completed successfully for user: {user.email} (UID: {user.firebase_uid})")
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
