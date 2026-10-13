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
             (REST: /health, /api/me)
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
   - Migrations: Alembic migrations (`0001_baseline`, `0002_create_users_table`, `0003_criteria_evaluations`, `0004_document_pages`), applied automatically on container startup.
   - User Profile Model: `User` model with UUID primary key, unique `firebase_uid`, `email`, `display_name`, `role` (`user_role` enum: `facilities_manager`, `procurement`, `approver`), timestamps.
   - Evaluation Criteria Model: `EvaluationCriterion` with UUID primary key, `user_id` (fk users), `kind` (builtin/custom), `builtin_key`, `name`, `guidance`, `weight` (0–100), `position`. Read-or-create on GET /api/criteria for 5 built-in items; atomic PUT with 422 validations.
   - Evaluation Models: `Evaluation`, `Vendor`, `Document`, `DocumentPage` (unique `(document_id, page_number)` with cascade delete), `Requirement`, `AnalysisJob`, `Finding`, `CriterionScore`, `CostBreakdown`, `Clarification` all scoped to authenticated user with cascade delete.
   - Scoring Engine: Pure Python functions in `app/services/scoring.py` computing points and totals dynamically using exact `Decimal` arithmetic. Round half-up applied strictly for display: points to 1 decimal, totals to whole numbers. Stored data holds only raw criterion scores; points and totals are never stored.
   - Document Validator & Ingestion: Byte signature checking (`%PDF-` with `pdfplumber` page counting <= 30 pages; DOCX ZIP archive containing `word/document.xml`). Local DOCX conversion (`app/services/ingestion.py`) reads body elements in reading order (`## <heading>` for headings, ` | ` joined cells for tables) into a single `page_number = 1`.
   - Auth layer: Firebase Admin SDK validating Bearer tokens; environment-driven initialization (emulator mode when FIREBASE_AUTH_EMULATOR_HOST is set, Application Default Credentials ADC when absent; fails fast in production if emulator is set).
   - AI / Gemini Client (`app/llm/client.py`): Official `google-genai` SDK (`GEMINI_API_KEY`, `GEMINI_MODEL` default `gemini-3.6-flash`). Exposes `GeminiClient` interface with `pdf_to_pages(pdf_bytes)` and `extract_requirements(pages)`, backed by `GoogleGenAIClient` and `FakeGeminiClient`, created via factory `create_gemini_client()`. Enforces Pydantic response schemas, 120s per-call timeout, up to 3 retries with exponential backoff on rate-limit/5xx/timeouts, and 1 retry on invalid JSON output. Prompts (`app/llm/prompts/`) place fixed instructions first and isolate untrusted document text in a clearly marked data section.
   - Isolated Worker & Job Launcher (`app/services/worker.py`, `app/services/job_launcher.py`):
     - `run_job_by_id(job_id, session_factory, gemini_client_factory)` has zero FastAPI imports or request ties, opening and closing its own DB sessions and storing all state in PostgreSQL.
     - `InProcessJobLauncher` runs `run_job_by_id` as an `asyncio.Task` and keeps a strong reference until completion. Tests override `get_job_launcher` with `InlineJobLauncher` using `FakeGeminiClient`.
     - **Path to a separate worker container**: A dedicated worker process can poll `analysis_jobs` for `status = 'queued'` using `SELECT ... FOR UPDATE SKIP LOCKED` and invoke the exact same `run_job_by_id` function, while `JobLauncher.launch()` becomes a no-op.
     - **Cloud Run deployment requirement (Phase 5)**: When running `InProcessJobLauncher` inside the `api` container on Cloud Run, the service requires CPU always allocated (`--no-cpu-throttling`) and `min-instances=1` / `max-instances=1` so background `asyncio` tasks are not throttled after HTTP 202 returns and startup recovery does not race active jobs on sibling instances.
     - **Startup Recovery**: `recover_interrupted_jobs(session_factory)` runs on API startup (and is callable from a standalone worker), marking any jobs still in `queued`/`extracting`/`analysing` as `failed` and any documents in `extracting` as `error` with message `"Interrupted — please start again"`.
   - Storage layer: Swappable storage interface (`StorageService`) with local disk implementation (`LocalStorageService`) writing to `./uploads`.
   - Endpoints:
     - `GET /health`, `GET /api/health`: Public, returns `{"status": "ok", "db": "ok"}`.
     - `GET /api/me`, `PUT /api/me`: User profile.
     - `GET /api/criteria`: Read-or-create user evaluation criteria.
     - `PUT /api/criteria`: Atomic criteria set replacement with strict 422 validations.
     - `GET /api/evaluations`: List evaluations and dynamically computed KPIs (`total`, `needs_action`, `analysed`, `open_clarifications`).
     - `POST /api/evaluations`: Create evaluation with 2–3 vendors.
     - `GET / PATCH / DELETE /api/evaluations/{id}`: Evaluation CRUD with storage file cleanup on delete.
     - `POST / DELETE /api/evaluations/{id}/documents`: Content-based validation and replacement (409 while a job is active; cascade-deletes `document_pages`).
     - `POST /api/evaluations/{id}/extract`: Starts `extract_requirements` background job (202 Accepted; 422 if docs missing; 409 if job active or user-edited requirements exist without `confirm_replace=true`).
     - `GET / PUT /api/evaluations/{id}/requirements`: Atomic requirements replacement (`analysed` -> `stale`).
     - `GET /api/evaluations/{id}/jobs/latest`: Latest background analysis job status, step_label, error_message, and timestamps.
     - `GET /api/evaluations/{id}/results`: Compliance matrix, costs, clarifications, and scoring with raw and display values.
     - Bare `/me`: Removed (returns 404).
   - Depends on healthy `postgres` and `firebase-auth-emulator`.

4. **`web` (`vixenone-web`)**:
   - React 18, Vite 5, TypeScript 5 dev server on `5173`.
   - Polling file-watcher enabled (`usePolling: true`) for Docker live-reload.
   - Design tokens: CSS custom properties (`--navy: #142B45`, `--accent: #FF7A1A`, `--ring: #142B45`, `--lifecycle-blue: #2563EB`, `--background`, `--surface`, `--status-*`, `--severity-*`), zero indigo across codebase. Primary buttons use accent bg with navy text. Status components strictly decoupled from orange accent.
   - Brand assets: Mark (`/mark.png`) used exclusively as favicon, and single tagline-free full logo (`/logo.png`) in `frontend/public/` rendered at fixed height 32px in header and 40px in auth/landing nav and footer. Wordmark image removed.
   - Router: React Router Data Router (`createBrowserRouter`, `RouterProvider`) with navigation blocking (`useBlocker`) for unsaved changes protection on form/settings/profile routes.
   - Live Routes:
     - `/`: Public landing page (`LandingPage`).
     - `/sign-in`, `/sign-up`: Authentication (`AuthPage`, S1/S1b).
     - `/evaluations`: Evaluations list dashboard (`EvaluationsListPage`, S2) with KPI filter tiles, search, status filter, and lifecycle-aware row navigation (`draft` -> `/upload`, `requirements_review` or `stale` -> `/requirements`, `analysed` -> `/comparison`).
     - `/evaluations/new`: Create evaluation form (`NewEvaluationPage`, S3) with 2–3 vendor names.
     - `/evaluations/:id/upload`: Document upload slots (`NewEvaluationPage`, S3) with client file checks, S3-error row display, file deletion, requirement extraction job trigger (`POST /api/evaluations/:id/extract` with 409 user-edit confirmation and active-job attach), 2s polling (`GET /api/evaluations/:id/jobs/latest`) with unmount cleanup, and live per-document lifecycle status (`Uploaded`, `Reading`, `Ready`, `Error`).
     - `/evaluations/:id/requirements`: Requirements review screen (`RequirementsReviewPage`, S4) nested under `EvaluationLayout` (which owns `evaluationDetail`, `savedRequirementCount`, and `savedMandatoryCount` via a memoized outlet context and a stable `refresh` callback). `RequirementsReviewPage` fetches only the requirements list once per evaluation ID, reads evaluation detail from context, keeps its own live count line for unsaved edits, and calls `refresh` only after a successful batch `PUT /api/evaluations/:id/requirements` save or after starting re-run extraction.
     - `/settings`: Evaluation criteria configuration (`SettingsPage`) with built-in/custom rows, inline validation, live weight sum=100 enforcement, and reset to defaults.
     - `/profile`: User profile management (`ProfilePage`) with name and role editing, read-only email, inline success/validation states, live header synchronization, and unsaved changes guard.
   - API Client: Typed `ApiClient` in `frontend/src/lib/api/client.ts` with TypeScript types generated via pinned `openapi-typescript` (`frontend/src/lib/types/`), supporting token injection and structured 422 validation error mapping.
   - UI Primitives: shadcn/ui components in `frontend/src/components/ui/` including `Carousel` (touch/swipe, keyboard navigation, auto-advance, reduced-motion).
   - Status components: `FindingStatusBadge`, `LifecycleStatus`, `RiskBadge`, `MandatoryTag` in `frontend/src/components/status/`.
   - Landing Page: Public root route `/` rendering responsive landing page with sticky 64px header, scroll-spy section links, framed hero 3-vendor compliance comparison card, 3-step How It Works, 6-feature grid, Showcase screenshot carousel, Who It's For role carousel, Principle band, FAQ accordion, CTA, and footer.
   - App Shell: `Header` (fixed 56px, single full logo image, user dropdown with live Profile navigation calling `/api/me`), `Sidebar` (expanded 240px with "+ New evaluation", "Evaluations", "RECENT" mock list, live Settings link, pinned Help; collapsed 64px tooltip mode, state persisted in `localStorage`), `AppShell` with full-screen layout and 520px slide-out drawer `Sheet`.
   - Authentication & Profile: Firebase JS SDK with environment-driven emulator detection (`initFirebaseAuth`), `AuthContext`, route guard `RequireAuth`, `AuthPage` sign-in/sign-up tab switcher with URL synchronization (`/sign-in`, `/sign-up`), email/password registration with display name and `PUT /api/me` profile creation, Google popup sign-in with default role, central `ROLE_LABELS` mapping, and dynamic `Header` user profile rendering without reload.
   - Mock Data Module: Strongly-typed demo dataset with 4 evaluations, 3 vendors, 8 requirements, 8x3 compliance matrix, cost breakdown with 18% GST, and deterministic scoring (64 / 86 / 58). (Isolated; not imported by live settings, profile, list, or create/upload pages).
   - Depends on healthy `api`.

## Startup Sequence & Healthchecks

1. `postgres` and `firebase-auth-emulator` boot and become healthy.
2. `api` starts, runs `alembic upgrade head`, starts Uvicorn, and passes its healthcheck.
3. `web` starts Vite and connects to `api`.
