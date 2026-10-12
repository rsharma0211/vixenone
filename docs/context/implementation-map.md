# Implementation Map

Per-component status, locations, responsibilities, and known gaps.
Statuses: `done` · `partial` · `stub`

| Component | Responsibility | Location | Status | Known Gaps |
| --- | --- | --- | --- | --- |
| Local Stack Orchestration | Docker Compose configuration for web, api, postgres, and firebase-auth | `docker-compose.yml`, `Makefile` | `done` | None |
| Database Service | PostgreSQL 16 Alpine with named volume persistence & healthcheck | `docker-compose.yml` (`postgres`) | `done` | None |
| Database Layer & Migrations | SQLAlchemy 2 async engine, psycopg 3, Alembic with baseline migration | `backend/app/core/database.py`, `backend/alembic/` | `done` | Product models coming in P3 |
| Auth Dependency & /me | Environment-driven Firebase Admin SDK init, ID-token verification, `get_current_user` dependency, `/me` endpoint | `backend/app/core/auth.py`, `backend/app/main.py` | `done` | None |
| Storage Service | Swappable file storage interface & LocalStorageService writing to `./uploads` | `backend/app/services/storage.py` | `done` | Cloud GCS storage adapter in future prompt |
| Frontend Foundation | Design tokens, shadcn/ui primitives, reusable status components, responsive app shell, router & auth guard, S1 sign-in, typed mock data, dev showcase | `frontend/src/` | `done` | None |
| Firebase Auth Emulator | Local Auth emulator on 9099 with UI on 4000 (Firestore & Storage removed) | `infra/docker/firebase/`, `firebase.json` | `done` | None |
| Seed Script | Idempotent demo user creation in Auth emulator | `scripts/seed.py`, `scripts/seed.sh` | `done` | None |
| Context Documentation | Architecture, implementation map, decisions tracking | `docs/context/` | `done` | Ongoing updates as features develop |
