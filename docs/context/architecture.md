# Architecture

## Containers & Services

The local development stack consists of four Docker containers on a shared bridge network (`vixenone-net`):

```
                        +----------------------------+
                        |      Host Browser / OS     |
                        +--------------+-------------+
                                       |
           +-------------------+-------+-----------+--------------------+
           | 5173              | 8000              | 5432               | 4000 (UI), 9099 (Auth)
           v                   v                   v                    v
+-------------------+  +-------------------+  +---------------+  +------------------------+
|        web        |  |        api        |  |   postgres    |  | firebase-auth-emulator |
|  Node 20 / Vite   |  |  Python 3.12 /    |  | PostgreSQL 16 |  |  firebase-tools       |
|  React + TS       |  |  FastAPI / Uvicorn|  |               |  |  (Auth only)           |
+-------------------+  +-------------------+  +---------------+  +------------------------+
           |                   |                      ^                    ^
           |                   +----------------------+                    |
           |                     (SQLAlchemy / psycopg 3)                  |
           |                   +-------------------------------------------+
           |                     (Token verification via Admin SDK)
           +-------------------+
             (REST: /health, /me)
```

1. **`postgres` (`vixenone-postgres`)**:
   - PostgreSQL 16 Alpine.
   - Listens on `5432`.
   - Data stored in named Docker volume `postgres_data`.
   - Healthcheck: `pg_isready -U vixenone -d vixenone`.

2. **`firebase-auth-emulator` (`vixenone-firebase-auth`)**:
   - Debian slim image with Node 20 and Firebase CLI (`firebase-tools`).
   - Runs **Auth emulator only** on `9099` and Emulator UI on `4000` (Firestore and Storage emulators removed).
   - Project ID: `demo-vixenone`.
   - Persistence: Mounted volume `./emulator-data:/emulator-data`.

3. **`api` (`vixenone-api`)**:
   - Python 3.12-slim, FastAPI, Uvicorn with `--reload`.
   - Listens on `8000`.
   - Data layer: SQLAlchemy 2 (async engine via `psycopg` 3) with shared session provider.
   - Migrations: Alembic with baseline migration (`0001_baseline`), applied automatically on container startup.
   - Auth layer: Firebase Admin SDK validating Bearer tokens; environment-driven initialization (emulator mode when FIREBASE_AUTH_EMULATOR_HOST is set, Application Default Credentials ADC when absent; fails fast in production if emulator is set).
   - AI settings: GEMINI_API_KEY (SecretStr) and GEMINI_MODEL (default gemini-3.6-flash) wired to configuration.
   - Storage layer: Swappable storage interface (`StorageService`) with local disk implementation (`LocalStorageService`) writing to `./uploads`.
   - Endpoints:
     - `GET /health`: Public, returns `{"status": "ok", "db": "ok"}`.
     - `GET /me`: Protected by Firebase ID token Bearer check, returns `{"uid": ..., "email": ..., "display_name": ...}`.
   - Depends on healthy `postgres` and `firebase-auth-emulator`.

4. **`web` (`vixenone-web`)**:
   - React 18, Vite 5, TypeScript 5 dev server on `5173`.
   - Polling file-watcher enabled (`usePolling: true`) for Docker live-reload.
   - Design tokens: CSS custom properties (`--background`, `--surface`, `--accent`, `--status-*`, `--severity-*`), 0 raw hex colours in component code, Inter font with tabular numbers.
   - UI Primitives: shadcn/ui components in `frontend/src/components/ui/` including `Carousel` (touch/swipe, keyboard navigation, auto-advance, reduced-motion).
   - Status components: `FindingStatusBadge`, `LifecycleStatus`, `RiskBadge`, `MandatoryTag` in `frontend/src/components/status/`.
   - Landing Page: Public root route `/` rendering responsive landing page with sticky 64px header, scroll-spy section links, framed hero 3-vendor compliance comparison card, 3-step How It Works, 6-feature grid, Showcase screenshot carousel, Who It's For role carousel, Principle band, FAQ accordion, CTA, and footer.
   - App Shell: `Header` (fixed 56px, wordmark, user dropdown calling `/api/me`), `Sidebar` (expanded 240px with "+ New evaluation", "Evaluations", "RECENT" mock list, pinned Settings/Help; collapsed 64px tooltip mode, state persisted in `localStorage`), `AppShell` with full-screen layout and 520px slide-out drawer `Sheet`.
   - Evaluation Layout: `EvaluationLayout` with breadcrumbs, title, meta line, and tab routes (`requirements`, `comparison`, `recommendation`).
   - Authentication: Firebase JS SDK with environment-driven emulator detection (`initFirebaseAuth`), `AuthContext`, route guard `RequireAuth`, and S1/S1b sign-in/sign-up page with email/password and emulator Google popup.
   - Mock Data Module: Strongly-typed demo dataset with 4 evaluations, 3 vendors, 8 requirements, 8x3 compliance matrix, cost breakdown with 18% GST, and deterministic scoring (64 / 86 / 58).
   - Depends on healthy `api`.

## Startup Sequence & Healthchecks

1. `postgres` and `firebase-auth-emulator` boot and become healthy.
2. `api` starts, runs `alembic upgrade head`, starts Uvicorn, and passes its healthcheck.
3. `web` starts Vite and connects to `api`.
