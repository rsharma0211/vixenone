# VixenOne

VixenOne is an AI-powered vendor-proposal evaluator for facilities and housekeeping services.

## Architecture Overview

- **Authentication**: Firebase Auth (runs offline using the Firebase Auth Emulator).
- **Application Data**: PostgreSQL 18 (persisted in a named Docker volume).
- **File Storage**: Local filesystem disk storage (`./uploads` mounted into API).
- **Backend**: FastAPI (Python 3.12) with SQLAlchemy 2, async psycopg 3, and Alembic migrations.
- **Frontend**: React + Vite + TypeScript.

No GCP credentials or internet access to cloud Firebase are required. The entire stack runs offline locally.

## Prerequisites

- **Docker** and **Docker Compose v2+** installed and running.
- **Python 3** (optional, for running `./scripts/seed.py` directly from host, or run via `make seed`).

## Quick Start

1. Start all services:
   ```bash
   make up
   ```
2. Seed the demo user:
   ```bash
   make seed
   ```
3. Open the web interface at [http://localhost:5173](http://localhost:5173).

## Services & Ports

| Service | Port / URL | Description |
| --- | --- | --- |
| **Web (Frontend)** | [http://localhost:5173](http://localhost:5173) | React + Vite + TypeScript application with hot module reload |
| **API (Backend)** | [http://localhost:8000](http://localhost:8000) | FastAPI application (`/health`, `/api/health`, `/api/me`) |
| **PostgreSQL** | `localhost:5432` | PostgreSQL 18 database (`vixenone` database, user `vixenone`) |
| **Firebase Auth Emulator** | `localhost:9099` | Local Firebase Authentication |
| **Firebase Emulator UI** | [http://localhost:4000](http://localhost:4000) | Web console for inspecting Auth emulator accounts |

## Commands

| Command | Action |
| --- | --- |
| `make up` | Builds images and starts all 4 services in the background. |
| `make down` | Gracefully stops all services. Persists Auth emulator data and PostgreSQL. |
| `make logs` | Follows logs from all running containers. |
| `make seed` | Creates the demo user (`demo@vixenone.app` / `demo1234`, Priya Sharma) in Auth emulator. Idempotent. |
| `make reset` | Stops containers, wipes database volume, emulator data, and `./uploads`, then restarts fresh and applies migrations. |
| `make migrate` | Applies any pending Alembic migrations. |
| `make db-shell` | Launches a `psql` interactive terminal inside the PostgreSQL container. |
| `make test` | Runs backend unit tests inside the API container. |

## Cloud tools

Containerized runner for Google Cloud SDK (`gcloud`) and Firebase CLI tools without requiring host installations:

- `make cloud-login` — Runs `gcloud auth login` (no-launch-browser flow), `gcloud auth application-default login` (no-launch-browser flow), and `firebase login` (no-localhost flow).
- `make cloud-config` — Sets the gcloud project to `vixenone` and region to `asia-south1`.
- `make cloud-check` — Prints the active account and project, and lists Cloud SQL instances, Cloud Storage buckets, Secret Manager secrets (names only), and Firebase projects.

## Deploy

Production deployment uses only Google Cloud and Firebase tools:

1. **One-time setup (Google tools only)**:
   - Authenticate tools:
     ```bash
     make cloud-login
     ```
   - Configure project and region:
     ```bash
     make cloud-config
     ```
   - Verify infrastructure and credentials:
     ```bash
     make cloud-check
     ```
   - Set the `PROD_*` variables in `.env` (project ID, region, artifact repo, Cloud SQL connection, service account, bucket, model, Firebase credentials). Ensure Secret Manager contains `GEMINI_API_KEY` and `DATABASE_URL`.
   - Verify configuration:
     ```bash
     make deploy-config
     ```

2. **Deploy to production (no `make up` needed)**:
   The local Compose stack does not need to be running. Frontend builds run in an isolated one-off container without starting dependent services or publishing ports.

   - **Deploy everything (full stack)**:
     ```bash
     make deploy
     ```
     (Supports `make deploy DRY_RUN=1` to preview all commands without modifying cloud resources).
     This executes in strict sequence, stopping immediately on any error:
     - Configuration validation (`deploy-config`, masks secrets)
     - Production API image build with Cloud Build (`build-api`)
     - Database migrations execution via Cloud Run prepare job (`migrate`)
     - Cloud Run service deployment for `vixenone-api` (`deploy-api`)
     - Frontend production build in one-off container (`build-web`, deletes previous build output first)
     - Bundle validation (`bundle-check`, verifies production API key presence and rejects test tokens/localhost URLs)
     - Firebase Hosting deployment (`deploy-web`)
     - Smoke test verification (`prod-smoke`)

   - **Deploy web only**:
     ```bash
     make deploy-web
     ```
     (Supports `make deploy-web DRY_RUN=1`).
     Always runs `build-web` in a one-off container, runs `bundle-check` to verify credentials, and only then deploys to Firebase Hosting. There is no way to deploy without building and verifying first.

3. **Seed demo data (first deploy only)**:
   ```bash
   make prod-seed
   ```
   > **Note:** Re-seeding wipes existing demo-user evaluations. You will be prompted to confirm by typing the production project ID from an interactive terminal. If no terminal is available, the command aborts. This is never run automatically as part of `make deploy`.

4. **Verify production health**:
   ```bash
   make prod-smoke
   ```
   Checks that `https://<project>.web.app/api/health` returns HTTP 200 and unauthenticated `/api/me` returns HTTP 401.

## How to Reset Data

To wipe all local state (Postgres database volume, Auth emulator accounts, and local uploads) and start fresh:
```bash
make reset
```

## Documentation Structure

- `docs/design/` - Design artifacts and UI/UX documentation.
- `docs/context/` - Architectural records, decisions log, and implementation map (`AGENTS.md` context docs).
