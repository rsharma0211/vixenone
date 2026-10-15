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
|  Node 20 / Vite   |  |  Python 3.12 /    |  | PostgreSQL 18 |  |  firebase-tools       |
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
   - PostgreSQL 18 Alpine.
   - Listens on `5432`.
   - Data stored in named Docker volume `postgres_18_data` (mounted at `/var/lib/postgresql/18/docker`).
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
   - Migrations: Alembic migrations (`0001_baseline`, `0002_create_users_table`, `0003_criteria_evaluations`, `0004_document_pages`, `0005_companies_locations`, `0006_phase4_analysis`), applied automatically on container startup.
   - Company & Location Models: `Company` (`id`, nullable `name` <= 120 chars, timestamps) and `Location` (`id`, `company_id` FK `companies.id` `ON DELETE CASCADE`, `name` 1–80 chars, `city` 1–80 chars, `position`, timestamps, unique `(company_id, lower(name))`). Every user belongs to a company (`users.company_id` NOT NULL FK `companies.id`; backfilled one company per existing user in `0005`, team-ready shape allowing multiple users per company later).
   - User Profile Model: `User` model with UUID primary key, `company_id` (FK `companies.id`), unique `firebase_uid`, `email`, `display_name`, `role` (`user_role` enum: `facilities_manager`, `procurement`, `approver`), timestamps. Creating a profile on `/api/me` or `/api/company` concurrency-safely creates and links a company (`name = null`).
   - Evaluation Criteria Model: `EvaluationCriterion` with UUID primary key, `user_id` (fk users), `kind` (builtin/custom), `builtin_key`, `name`, `guidance`, `weight` (0–100), `position`. Read-or-create on GET /api/criteria for 5 built-in items; atomic PUT with 422 validations; frozen into criteria snapshot on analysis start.
   - Evaluation Models: `Evaluation` (with nullable `location_id` FK `locations.id` `ON DELETE RESTRICT`), `Vendor`, `Document`, `DocumentPage` (unique `(document_id, page_number)` with cascade delete), `Requirement`, `AnalysisJob`, `Finding` (with indexed `criterion_key`), `CriterionScore`, `CostBreakdown` (with nullable `monthly_base`, `gst_18`, `monthly_total`), `Clarification` all scoped to authenticated user with cascade delete.
   - Scoring & Recommendation Engine: Pure Python functions in `app/services/scoring.py` computing raw 0–100 scores for every criteria snapshot key per vendor:
     - Status mapping: `compliant` 100, `partially_compliant` 50, `non_compliant` 0, `not_evidenced` 0.
     - `mandatory_compliance`: average status score over mandatory requirements (100 if none mandatory).
     - Judged criteria (`service_coverage`, `sla_operational`, custom): status score of criterion finding (0 if missing).
     - `cost_comparability`: `100 - 40` (if monthly base missing) `- 15` per unknown cost item (floor 0).
     - `unresolved_risks`: `100 - (high 20, medium 10, low 5)` per finding/risk with any risk type (floor 0).
     - Recommendation: recommends the top eligible vendor (no mandatory failure) by exact total if >= 2 vendors analysed AND no mandatory `not_evidenced` AND no mandatory `needs_review` AND no tie on exact total; otherwise `insufficient` with explanatory reasons.
     - Points and totals are dynamically computed on read via exact `Decimal` arithmetic. Round half-up applied strictly for display: points to 1 decimal, totals to whole numbers.
   - Quote Verification Engine (`app/services/verification.py`): Python-based quote normalisation (whitespace/linebreak collapsing, joining hyphenated linebreaks, unifying curly quotes and dashes, case-insensitive, dehyphenation fallback). Checks cited page, scans other pages of the document (auto-correcting page number), and downgrades to `needs_review = true` when quote is missing/invented.
   - Document Validator & Ingestion: Byte signature checking (`%PDF-` with `pdfplumber` page counting <= 30 pages; DOCX ZIP archive containing `word/document.xml`). Local DOCX conversion (`app/services/ingestion.py`) reads body elements in reading order (`## <heading>` for headings, ` | ` joined cells for tables) into a single `page_number = 1`.
   - Auth layer: Firebase Admin SDK validating Bearer tokens; environment-driven initialization (emulator mode when FIREBASE_AUTH_EMULATOR_HOST is set, Application Default Credentials ADC when absent; fails fast in production if emulator is set).
   - AI / Gemini Client (`app/llm/client.py`): Official `google-genai` SDK (`GEMINI_API_KEY`, `GEMINI_MODEL` default `gemini-3.6-flash`). Exposes `GeminiClient` interface with `pdf_to_pages(pdf_bytes)`, `extract_requirements(pages)`, and `analyse_vendor(requirements, judged_criteria, proposal_pages)`. Prompts isolate inputs in marked, length-bounded sections (`MAX_REQUIREMENTS_SECTION_CHARS`, `MAX_CRITERIA_SECTION_CHARS`, `MAX_PROPOSAL_SECTION_CHARS`) and command the model to ignore in-document instructions and never calculate scores. Enforces Pydantic response schemas, 120s per-call timeout, up to 3 retries with exponential backoff on rate-limit/5xx/timeouts, and 1 retry on invalid JSON output.
   - Isolated Worker & Job Launcher (`app/services/worker.py`, `app/services/job_launcher.py`):
     - `run_job_by_id(job_id, session_factory, gemini_client_factory)` has zero FastAPI imports or request ties, opening and closing its own DB sessions and storing all state in PostgreSQL.
     - Parallel execution capped at 4 tasks for extraction and analysis.
     - Analysis job (`_run_analyse`): all-or-nothing atomic execution; if any vendor fails, job fails with zero database mutations; otherwise, all findings, costs, deduplicated clarifications, and raw criterion scores are persisted in a single transaction, setting evaluation status to `analysed`.
     - `InProcessJobLauncher` runs `run_job_by_id` as an `asyncio.Task` and keeps a strong reference until completion. Tests override `get_job_launcher` with `InlineJobLauncher` using `FakeGeminiClient`.
     - **Path to a separate worker container**: A dedicated worker process can poll `analysis_jobs` for `status = 'queued'` using `SELECT ... FOR UPDATE SKIP LOCKED` and invoke the exact same `run_job_by_id` function, while `JobLauncher.launch()` becomes a no-op.
     - **Cloud Run deployment requirement (Phase 5)**: When running `InProcessJobLauncher` inside the `api` container on Cloud Run, the service requires CPU always allocated (`--no-cpu-throttling`) and `min-instances=1` / `max-instances=1` so background `asyncio` tasks are not throttled after HTTP 202 returns and startup recovery does not race active jobs on sibling instances.
     - **Startup Recovery**: `recover_interrupted_jobs(session_factory)` runs on API startup (and is callable from a standalone worker), marking any jobs still in `queued`/`extracting`/`analysing` as `failed` and any documents in `extracting` as `error` with message `"Interrupted — please start again"`.
   - Storage layer: Swappable storage interface (`StorageService`) with local disk implementation (`LocalStorageService`) writing to `./uploads` and Google Cloud Storage adapter (`CloudStorageService`) via ADC, running blocking GCS operations off the event loop via `asyncio.to_thread`. Missing objects consistently raise `FileNotFoundError` (or return `False` on delete).
   - Caching: `NoCacheMiddleware` guarantees `Cache-Control: no-store` on every API response (including protected routes and error responses), preventing CDN/proxy caching of polling steps.
   - Run Modes:
     - `development`: migrations applied automatically on start, Uvicorn auto-reload enabled, port 8000.
     - `production`: no startup migrations, no auto-reload, single worker process (`--workers 1` for in-process background task isolation), listening on Cloud Run provided `$PORT` (fallback 8000).
   - Prepare Job: One-off command in the `api` image (`entrypoint.sh prepare` or `python -m app.cli.prepare`) running database migrations (`alembic upgrade head`) followed by the demo seed. Executed as a Cloud Run job; local `make migrate` and `make seed` use the exact same code paths.
   - Seed via Firebase Admin SDK: Idempotent demo user creation/retrieval (`demo@vixenone.app`, password `demo1234`, display name `Priya Sharma`) using Firebase Admin SDK (emulator locally, ADC in deploy without service account keys). Automatically creates or updates Postgres profile row (`role: facilities_manager`) matching `/api/me` keying (`firebase_uid`), then seeds company, locations, criteria, and full demo dataset.
   - Production Same-Origin Plan: Firebase Hosting hosts the frontend build and rewrites `/api/**` to the Cloud Run `api` service. Browser requests hit `/api/...` directly on the same origin (`https://<domain>/api/...`), rendering CORS unnecessary in production.
   - Endpoints:
     - `GET /health`, `GET /api/health`: Public, returns `{"status": "ok", "db": "ok"}`.
     - `GET /api/me`, `PUT /api/me`: User profile (read-or-creates user and company).
     - `GET /api/company`: Read-or-create user's company and list locations ordered by `position` with dynamically computed `evaluation_count`.
     - `PATCH /api/company`: Update company `name` (trimmed <= 120 chars; empty string stored as `null`).
     - `POST /api/company/locations`: Add location (`name` and `city` trimmed 1–80 chars, case-insensitive unique name per company -> 422, appended at next `position`, 201).
     - `PATCH /api/company/locations/{id}`: Update location `name` and/or `city` (404 if not in user's company).
     - `DELETE /api/company/locations/{id}`: Delete location if unused (204, re-numbers remaining positions without gaps); 409 `"Used by N evaluations."` if any evaluation references it.
     - `GET /api/criteria`: Read-or-create user evaluation criteria.
     - `PUT /api/criteria`: Atomic criteria set replacement with strict 422 validations.
     - `GET /api/evaluations`: List evaluations (including `location: {id, name, city} | null`) and dynamically computed KPIs (`total`, `needs_action`, `analysed`, `open_clarifications`).
     - `POST /api/evaluations`: Create evaluation in `draft` status with `title` and `category` required (`location_id` optional, validated against user's company or 422 `"Unknown location."`; `vendor_names` optional, 0–3; free-text `location` removed).
     - `GET / PATCH / DELETE /api/evaluations/{id}`: Evaluation CRUD with `location: {id, name, city} | null` in detail response, `location_id` support on `PATCH` (null clears, other company's -> 422 `"Unknown location."`), and storage file cleanup on delete.
     - `POST /api/evaluations/{id}/vendors`: Add a vendor (trimmed 1–80 chars, case-insensitive unique per evaluation, max 3 vendors -> 422 `"An evaluation can have at most 3 vendors."`, appended at next position; 409 while a job is active; transitions `analysed` -> `stale`).
     - `PATCH /api/evaluations/{id}/vendors/{vendor_id}`: Rename a vendor (trimmed 1–80 chars, case-insensitive unique per evaluation; 409 while a job is active; preserves evaluation status).
     - `DELETE /api/evaluations/{id}/vendors/{vendor_id}`: Remove a vendor and cascade-delete its proposal document, stored file via `StorageService`, `document_pages`, `findings`, `criterion_scores`, `cost_breakdowns`, and `clarifications` in one transaction; re-numbers remaining vendor positions without gaps; 409 while a job is active; transitions `analysed` -> `stale`.
     - `POST / DELETE /api/evaluations/{id}/documents`: Content-based validation and replacement (409 while a job is active; cascade-deletes `document_pages`).
     - `POST /api/evaluations/{id}/extract`: Starts `extract_requirements` background job (202 Accepted; 422 unless requirements doc uploaded, at least 2 vendors exist, and every vendor has a proposal, naming what is missing; 409 if job active or user-edited requirements exist without `confirm_replace=true`).
     - `GET / PUT /api/evaluations/{id}/requirements`: Atomic requirements replacement (`analysed` -> `stale`).
     - `POST /api/evaluations/{id}/analyse`: Starts `analyse` background job (202 Accepted; 422 naming missing items if <2 vendors, missing/not-ready requirements doc, missing/not-ready vendor proposals, or 0 requirements; 409 if active job; 409 if already `analysed` without `confirm_rerun=true`). Freezes criteria snapshot at start.
     - `PUT /api/evaluations/{id}/weights`: Updates criteria snapshot weights (422 if keys don't match snapshot or sum != 100; 409 if no snapshot). Recomputes totals without altering user's live criteria or evaluation status.
     - `GET /api/evaluations/{id}/jobs/latest`: Latest background analysis job status, step_label, error_message, and timestamps.
     - `GET /api/evaluations/{id}/results`: Compliance matrix findings, costs, deduplicated clarifications, per-vendor criterion scores and points, exact and display totals, mandatory counts (met/total, failures, not evidenced, needs review), recommendation ({state, vendor_id, reasons}), and company name for print header.
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
     - `/evaluations`: Evaluations list dashboard (`EvaluationsListPage`, S2) with KPI filter tiles, search, status filter, row subline showing `<location name>, <city> · N requirements` (or `· Not extracted yet`, omitting location when null), and lifecycle-aware row navigation (draft or active job -> `/documents`, `requirements_review` or `stale` -> `/requirements`, `analysed` -> `/comparison`).
     - `/evaluations/new`: Step 1 of two-step create (`NewEvaluationPage`): title, category, and optional location dropdown (`"No specific location"`, `"<name>, <city>"` in order, `"+ Add new location"` dialog via `AddLocationDialog`), opens the Documents tab.
     - `/evaluations/:id/documents`: Documents tab (`DocumentsPage`, S3), first of four tabs (Documents · Requirements · Comparison · Recommendation): requirements slot, vendor cards (rename/remove/add via `POST`/`PATCH`/`DELETE /vendors`), per-document upload/replace/delete, extract gating, 2s `jobs/latest` polling, confirmations via `ConfirmDialog`. `/evaluations/:id/upload` redirects here.
     - Unsaved-changes guard: `useUnsavedChangesGuard` (data router `useBlocker` + beforeunload) on Requirements, Profile and Settings (company name + criteria); re-run extraction always confirms and sends `confirm_replace: true`.
     - `/evaluations/:id/requirements`: Requirements review screen (`RequirementsReviewPage`, S4) nested under `EvaluationLayout` (which owns `evaluationDetail`, `savedRequirementCount`, and `savedMandatoryCount` via a memoized outlet context and a stable `refresh` callback, rendering header meta `<location name>, <city> · <category> · N requirements (M mandatory)` and omitting location when null). `RequirementsReviewPage` fetches only the requirements list once per evaluation ID, reads evaluation detail from context, keeps its own live count line for unsaved edits, and calls `refresh` only after a successful batch `PUT /api/evaluations/:id/requirements` save. Re-run extraction and Add requirement actions are removed from this tab and scoped to the Documents tab.
     - `/settings`: Company and Evaluation criteria configuration (`SettingsPage`) with Company section above Evaluation criteria (company name input with Save, locations table with inline add, inline rename, and `ConfirmDialog` delete disabled with tooltip when `evaluation_count > 0`) plus built-in/custom criteria rows, inline validation, live weight sum=100 enforcement, and reset to defaults.
     - `/profile`: User profile management (`ProfilePage`) with name and role editing, read-only email, inline success/validation states, live header synchronization, and unsaved changes guard.
   - API Client: Typed `ApiClient` in `frontend/src/lib/api/client.ts` with TypeScript types generated via pinned `openapi-typescript` (`frontend/src/lib/types/`), supporting token injection and structured 422 validation error mapping. In production builds, `BASE_URL` is empty (`""`) so all network calls target same-origin `/api/...` directly without CORS; local dev defaults to `VITE_API_BASE_URL`.
   - Production Build Guard: `frontend/vite.config.ts` validates at build time that `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, and `VITE_FIREBASE_PROJECT_ID` are present and fails fast if any are missing or if `VITE_FIREBASE_AUTH_EMULATOR_HOST` is set. Third-party library code (including Firebase Auth) remains untouched without chunk rewrite.
   - UI Primitives & KPI Tiles: shadcn/ui components in `frontend/src/components/ui/` including `Carousel` and `Tooltip`, plus reusable `KpiTile` (`frontend/src/components/KpiTile.tsx`) and central `KPI_HELP_TEXT` map (`frontend/src/lib/kpiHelp.ts`) required for all KPI and summary numbers across all screens (including Phase 4 comparison and recommendation summaries).
   - Status components: `FindingStatusBadge`, `LifecycleStatus`, `RiskBadge`, `MandatoryTag` in `frontend/src/components/status/`.
   - Landing Page: Public root route `/` rendering responsive landing page with sticky 64px header, scroll-spy section links, framed hero 3-vendor compliance comparison card, 3-step How It Works, 6-feature grid, Showcase screenshot carousel, Who It's For role carousel, Principle band, FAQ accordion, CTA, and footer.
   - App Shell: `Header` (fixed 56px, single full logo image, user dropdown with live Profile navigation calling `/api/me`), `Sidebar` (expanded 240px with "+ New evaluation", "Evaluations", "RECENT" mock list, live Settings link, pinned Help; collapsed 64px tooltip mode, state persisted in `localStorage`), `AppShell` with full-screen layout and 520px slide-out drawer `Sheet`.
   - Authentication & Profile: Firebase JS SDK with environment-driven emulator detection (`initFirebaseAuth`), `AuthContext`, route guard `RequireAuth`, `AuthPage` sign-in/sign-up tab switcher with URL synchronization (`/sign-in`, `/sign-up`), email/password registration with display name and `PUT /api/me` profile creation, Google popup sign-in (`signInWithPopup`) with default role, central `ROLE_LABELS` mapping, and dynamic `Header` user profile rendering without reload. Fake API key fallback is restricted strictly to local emulator dev and never included in production builds.
   - Mock Data Module: Strongly-typed demo dataset with 4 evaluations, 3 vendors, 8 requirements, 8x3 compliance matrix, cost breakdown with 18% GST, and deterministic scoring (64 / 86 / 58). (Isolated; not imported by live settings, profile, list, or create/upload pages).
   - Depends on healthy `api`.

5. **`cloud-tools` (Host Tools Runner)**:
   - On-demand container built from `infra/docker/tools/Dockerfile` based on `google/cloud-sdk:588.0.0-slim` with Node LTS (`node:24.21.0-bookworm-slim`) and Firebase CLI (`firebase-tools@15.33.0`).
   - Run via `scripts/cloud-tools.sh` mounting the repository at `/workspace` with interactive terminal pass-through (`-i` / `-it`).
   - Auth and session state persisted strictly in named Docker volumes (`vixenone_gcloud_config` at `/root/.config/gcloud`, `vixenone_firebase_config` at `/root/.config/configstore`, `vixenone_firebase_home` at `/root/.firebase`), keeping all cloud credentials off the repository filesystem.
   - Orchestrated via `make cloud-login`, `make cloud-config`, and `make cloud-check`.

## Startup Sequence & Healthchecks

1. `postgres` and `firebase-auth-emulator` boot and become healthy.
2. `api` starts, runs `alembic upgrade head`, starts Uvicorn, and passes its healthcheck.
3. `web` starts Vite and connects to `api`.

## Production Architecture & Deploy Topology

In production on Google Cloud:

1. **Firebase Hosting**:
   - Serves pre-built static frontend assets (`frontend/dist`) configured in `firebase.json` and `.firebaserc`.
   - Rewrites `/api/**` directly to the Cloud Run service `vixenone-api` in `asia-south1`.
   - Rewrites all other routes (`**`) to `/index.html` for single-page app routing.
   - Enforces `Cache-Control: max-age=0, no-cache, no-store, must-revalidate` for `index.html` and 1-year immutable caching for `/assets/**`.
   - Guarantees same-origin API access from the browser, eliminating CORS entirely.

2. **Cloud Run Service (`vixenone-api`)**:
   - Production API container built from multi-stage `backend/Dockerfile` target `production` containing runtime dependencies only (`pytest`, `ruff`, `mypy` absent).
   - Starts in production mode (`ENV=production`, `PORT` dynamic binding, 1 worker, no boot migrations, no auto-reload).
   - Resources: 1 GiB memory, 300 s request timeout, CPU always allocated (`--no-cpu-throttling`), min 1 and max 1 instance to isolate in-process background task execution.
   - Attachments: Cloud SQL PostgreSQL 18 instance connection via Unix socket; Secret Manager secrets mounted as environment variables (`GEMINI_API_KEY=GEMINI_API_KEY:latest`, `DATABASE_URL=DATABASE_URL:latest`).
   - Unauthenticated invocations permitted; token verification performed in-app via Firebase Admin SDK.

3. **Cloud Run Job (`vixenone-prepare`)**:
   - Dedicated prepare task reusing the production API image with args `prepare,migrate` (deploy-time schema migration) or `prepare,seed` (one-time demo user provisioning).
   - Attached to Cloud SQL and Secret Manager secrets with 0 retries and 10 minute timeout.

4. **Production Deploy Pipeline (`scripts/deploy.sh`)**:
   - Automated steps: `config` (validates `PROD_*` variables without exposing secrets), `build-api` (uncommitted tree refusal guard, Cloud Build container push to Artifact Registry), `migrate` (updates and executes prepare job), `deploy-api` (deploys Cloud Run service), `build-web` (production build in web container with Firebase build guard), `deploy-web` (Firebase Hosting deploy), `smoke` (verifies HTTP 200 on `/api/health` and HTTP 401 on unauthenticated `/api/me`), and `seed` (isolated demo data seeding with project confirmation).
   - Full dry-run execution simulation supported via `DRY_RUN=1`.

