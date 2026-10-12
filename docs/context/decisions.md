# Decisions Log

Append-only record of architectural and implementation decisions. Format: `YYYY-MM-DD — decision — reason`.

- 2026-10-12 — Use Docker Compose with Node 20, Python 3.12, and Firebase Emulator Suite — Provide completely offline local stack requiring zero real cloud credentials.
- 2026-10-12 — Enable Vite polling file-watch mode in Docker dev server — Ensure reliable hot module reloading across host volume mounts.
- 2026-10-12 — Firebase emulator export-on-exit with SIGTERM trap — Ensure auth state persists seamlessly across `docker compose down` and `up`.
- 2026-10-12 — Standalone Python urllib seed script — Eliminate dependency on heavy Firebase Admin SDK for local user provisioning.
- 2026-10-12 — Use PostgreSQL 16 for application data instead of Firestore (Firestore removed) — Relational data model and ACID transactions for evaluations, matrix compliance, and scoring.
- 2026-10-12 — Use Firebase Auth Emulator exclusively for identity — Retain Firebase token-based auth while decoupling database and storage from Google proprietary cloud databases.
- 2026-10-12 — Swappable StorageService interface with LocalStorageService — Local disk writes for local development with pluggable cloud adapter interface for later.
- 2026-10-12 — Environment-driven Firebase Admin initialization — Switch between emulator and ADC modes based purely on environment without service account keys, and fail fast in production if emulator is configured.
- 2026-10-12 — Consolidate agent rulebook into GEMINI.md with AGENTS.md pointer — Single source of truth for repository rules reflecting PostgreSQL, async SQLAlchemy, storage interface, and Gemini configuration.
- 2026-10-12 — Frontend foundation with CSS variables, shadcn/ui primitives, and environment-driven Firebase Auth SDK — Central design token enforcement without inline hex colours, strict user session guards, and persistent responsive shell.
- 2026-10-12 — Public landing page at root route with pure React shadcn-compatible carousel — Zero-dependency carousel honoring prefers-reduced-motion, auto-advance, and keyboard/touch navigation while reusing existing design tokens and status components.
- 2026-10-12 — PostgreSQL user profile table with concurrency-safe ON CONFLICT upsert and removal of bare /me route — Keep Firebase as the source of identity while storing profile and role data in Postgres, avoiding race conditions on concurrent first calls, and standardizing all profile access under /api/me.
- 2026-10-12 — Central UserRole and ROLE_LABELS map in frontend — Eliminate hard-coded role display strings across UI components and enforce single source of truth for role labels and enum values.
- 2026-10-12 — Mount-only auth redirect guard on sign-in / sign-up — Prevent premature auto-redirection during sign-up submission while PUT /api/me runs and preserve inline error display when profile updates fail.
- 2026-10-12 — User-scoped evaluation criteria with frozen snapshot key references — Criteria are isolated per user; evaluations freeze a snapshot of criteria on analysis start and reference keys (never live foreign keys) so criteria updates never alter existing evaluation matrices.
- 2026-10-12 — Deterministic scoring with exact Decimal arithmetic and round-half-up display — Pure python scoring module computes points and totals without calculation rounding; round-half-up display applies to points (1 dec) and totals (whole numbers); raw and display values returned; demo raw scores are seeded fixtures.
- 2026-10-12 — Content-based document upload validation with pdfplumber and zip inspection — Replaced PyMuPDF with pdfplumber for page counting up to 30 pages; DOCX requires valid ZIP with word/document.xml; file extensions ignored in favor of binary signature verification.
- 2026-10-12 — Phase 2 brand design tokens: Navy #142B45 and Orange #FF7A1A with zero indigo — Establish high-contrast brand palette with navy button text on orange, isolating status pill colours from brand orange.
- 2026-10-12 — Switch App router to React Router Data Router (createBrowserRouter) — Enable useBlocker hook for unsaved changes protection on criteria settings without third-party packages.
- 2026-10-12 — OpenAPI-generated types and typed ApiClient with 422 error mapper — Enforce end-to-end schema consistency from FastAPI Pydantic models to React forms and map field-level 422 errors directly to form inputs.

