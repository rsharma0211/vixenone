# Implementation Map

Per-component status, locations, responsibilities, and known gaps.
Statuses: `done` · `partial` · `stub`

| Component | Responsibility | Location | Status | Known Gaps |
| --- | --- | --- | --- | --- |
| Local Stack Orchestration | Docker Compose configuration for web, api, postgres, and firebase-auth | `docker-compose.yml`, `Makefile` | `done` | None |
| Database Service | PostgreSQL 16 Alpine with named volume persistence & healthcheck | `docker-compose.yml` (`postgres`) | `done` | None |
| Database Layer & Migrations | SQLAlchemy 2 async engine, psycopg 3, Alembic with baseline migration | `backend/app/core/database.py`, `backend/alembic/` | `done` | Product models coming in P3 |
| Auth Dependency & Identity | Environment-driven Firebase Admin SDK init, ID-token verification, `get_current_user` dependency | `backend/app/core/auth.py` | `done` | None |
| Storage Service | Swappable file storage interface & LocalStorageService writing to `./uploads` | `backend/app/services/storage.py` | `done` | Cloud GCS storage adapter in future prompt |
| Frontend Foundation | Design tokens, shadcn/ui primitives, reusable status components, responsive app shell, router & auth guard, S1 sign-in, typed mock data, dev showcase | `frontend/src/` | `done` | None |
| Firebase Auth Emulator | Local Auth emulator on 9099 with UI on 4000 (Firestore & Storage removed) | `infra/docker/firebase/`, `firebase.json` | `done` | None |
| Seed Script | Idempotent demo user creation in Auth emulator and Postgres profile synchronization | `scripts/seed.py`, `scripts/seed.sh` | `done` | None |
| Context Documentation | Architecture, implementation map, decisions tracking | `docs/context/` | `done` | Ongoing updates as features develop |
| User Profile & Identity | PostgreSQL `users` table, Alembic `0002_create_users_table`, `User` model, `UserRepository`, `UserService`, and protected `GET`/`PUT /api/me` | `backend/app/models/user.py`, `backend/app/schemas/user.py`, `backend/app/repositories/user_repo.py`, `backend/app/services/user_service.py`, `backend/app/api/users.py` | `done` | None |
| Public Landing Page (L0) | Public landing page at `/` with sticky header, scroll-spy navigation, hero comparison preview card, 3-step How It Works, 6-feature grid, Showcase screenshot carousel (auto-advance with hover/focus pause), Who It's For role carousel, Principle band, FAQ accordion, final CTA, and footer | `frontend/src/pages/LandingPage.tsx`, `frontend/src/components/ui/carousel.tsx`, `frontend/public/screenshots/` | `done` | None |
| Sign-up Flow & User Profile (S1/S1b) | S1/S1b sign-in / sign-up tab switching with URL sync (`/sign-in`, `/sign-up`), validation (email in use, password length, required fields), Firebase auth + PUT /api/me persistence, Google sign-up/in with default role, central `ROLE_LABELS` map, dynamic Header profile/role | `frontend/src/pages/S1.tsx`, `frontend/src/lib/auth/roles.ts`, `frontend/src/lib/auth/AuthContext.tsx`, `frontend/src/lib/api/client.ts`, `frontend/src/components/layout/Header.tsx` | `done` | None |
