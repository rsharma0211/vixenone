# Decisions Log

Append-only record of architectural and implementation decisions. Format: `YYYY-MM-DD — decision — reason`.

- 2026-10-12 — Use Docker Compose with Node 20, Python 3.12, and Firebase Emulator Suite — Provide completely offline local stack requiring zero real cloud credentials.
- 2026-10-12 — Enable Vite polling file-watch mode in Docker dev server — Ensure reliable hot module reloading across host volume mounts.
- 2026-10-12 — Firebase emulator export-on-exit with SIGTERM trap — Ensure auth state persists seamlessly across `docker compose down` and `up`.
- 2026-10-12 — Standalone Python urllib seed script — Eliminate dependency on heavy Firebase Admin SDK for local user provisioning.
- 2026-10-12 — Use PostgreSQL 16 for application data instead of Firestore — Relational data model and ACID transactions for evaluations, matrix compliance, and scoring.
- 2026-10-12 — Use Firebase Auth Emulator exclusively for identity — Retain Firebase token-based auth while decoupling database and storage from Google proprietary cloud databases.
- 2026-10-12 — Swappable StorageService interface with LocalStorageService — Local disk writes for local development with pluggable cloud adapter interface for later.
