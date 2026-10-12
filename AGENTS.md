# AGENTS.md — VixenOne

Rulebook for every coding agent working in this repo (Antigravity, Gemini CLI).
Read this file fully before every task. If a task conflicts with this file, stop and report the conflict.

---

## 1. Purpose

VixenOne is an AI-powered vendor-proposal evaluator for facilities / housekeeping services.
A user uploads one requirements document and 2–3 vendor proposals. The system returns:

- an evidence-backed compliance matrix (requirement × vendor)
- gaps and risks (exclusions, omissions, ambiguity, contradictions, unknown costs)
- a cost comparison in INR on a common monthly basis
- deterministic weighted scores
- clarification questions linked to gaps
- a recommendation (which may be "insufficient information")
- a printable report

**Product principle:** never just say which vendor looks best. Show what each vendor explicitly
committed to, what is unknown, what is risky, and what must be clarified.

Prototype for the AI Builder Cup. Demo: 18 October 2026. Demo setting: Mumbai office,
monthly housekeeping contract, INR, GST shown separately.

---

## 2. Non-negotiables

Breaking any of these is a failed task, even if tests pass.

1. **No invented facts.** No price, quantity, SLA, or commitment may appear unless it is in a source document.
   Unquantified costs are `unknown`, never estimated.
2. **Every finding is evidence-verified in code.** A finding's quote must exist (normalised whitespace,
   case-insensitive) inside the segment it cites. If not, the finding is downgraded to `Not evidenced`
   and flagged `needs_review`. The model's own confidence is never the check.
3. **Scoring is deterministic Python.** No model call participates in any score, weight, total, or ranking.
   Same inputs + same weights = same output, always.
4. **Mandatory failures are never hidden.** They are reported separately from the total score.
   A vendor with a mandatory failure cannot be recommended without that failure shown next to it.
5. **Every data access is scoped to the signed-in user.** Every API route requires a verified Firebase ID
   token. Every Firestore read/write goes under that user's ID. No route returns another user's data.
6. **Fact vs inference is explicit.** Any statement not directly quoted is labelled `inference`.
7. **Failures are visible.** Extraction or analysis failures are surfaced to the user. Nothing fails silently.
8. **Google products only** for runtime and cloud services. Open-source libraries are fine.
   Never add a non-Google cloud service or API.

---

## 3. Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind CSS, shadcn/ui, React Router, TanStack Query, Firebase JS SDK |
| Frontend serving | nginx (serves build, proxies `/api` to backend) |
| Backend | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX) |
| AI | Gemini via `google-genai` SDK — AI Studio key locally, Vertex AI on Cloud Run |
| Auth | Firebase Authentication (Google sign-in + email/password) |
| Data | Firestore |
| Local | Docker Compose: frontend, backend, Firebase Auth emulator, Firestore emulator |
| Cloud | Cloud Run (2 services), Artifact Registry, Secret Manager, Cloud Build |
| Tests | pytest (backend), recorded Gemini fixtures |

Do not add dependencies without recording the reason in `docs/context/decisions.md`.

---

## 4. Repository layout

```
/
├── AGENTS.md                 # this file
├── GEMINI.md                 # points to AGENTS.md
├── Makefile
├── docker-compose.yml
├── .env.example              # only template; real .env never committed
├── firebase.json             # emulator config
├── frontend/
│   ├── nginx.conf
│   └── src/
│       ├── pages/            # one folder per screen
│       ├── components/       # shared components
│       ├── components/ui/    # shadcn/ui primitives
│       ├── lib/api/          # API client
│       ├── lib/auth/         # Firebase auth wrapper
│       └── lib/types/        # GENERATED from backend OpenAPI — never hand-edit
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/              # FastAPI routers only; thin
│   │   ├── core/             # config, auth dependency, errors, logging
│   │   ├── schemas/          # Pydantic models — single source of truth
│   │   ├── services/         # ingestion, requirements, analysis, verification, costs, scoring, synthesis
│   │   ├── llm/              # the ONLY place that calls Gemini
│   │   │   └── prompts/      # versioned prompt files
│   │   └── repositories/     # Firestore access only
│   └── tests/
│       ├── unit/
│       └── fixtures/llm/     # recorded Gemini responses
├── dataset/
│   ├── requirements/
│   ├── proposals/
│   └── expected/             # ground truth — READ ONLY for agents
├── eval/                     # eval harness vs ground truth
├── infra/                    # Cloud Run deploy scripts
└── docs/
    ├── context/
    │   ├── implementation-map.md
    │   ├── architecture.md
    │   └── decisions.md
    └── submission/
```

Keep this layout. If a new top-level folder is needed, record why in `decisions.md`.

---

## 5. Commands

| Command | Does |
| --- | --- |
| `make up` | Start full local stack (frontend, backend, emulators) |
| `make down` | Stop local stack |
| `make test` | Run backend unit tests (no live model calls) |
| `make eval` | Run pipeline on `dataset/` with live Gemini; compare to `dataset/expected/` |
| `make types` | Regenerate frontend types from backend OpenAPI |
| `make lint` | Lint backend and frontend |
| `make seed` | Create demo user in Auth emulator |

Every task ends with `make test` passing. Tasks touching schemas also run `make types`.

---

## 6. Domain rules

### Compliance statuses (exact values)
`Compliant` · `Non-compliant` · `Partially compliant` · `Not evidenced`

- `Compliant` — proposal explicitly supports the requirement. Evidence required.
- `Non-compliant` — proposal explicitly conflicts. Show both the requirement and the conflicting quote.
- `Partially compliant` — some elements covered. List covered and uncovered elements.
- `Not evidenced` — not enough information. Never assume either way. Always generates a clarification question.

### Risk / finding types (exact values)
`Exclusion` · `Omission` · `Ambiguity` · `Contradiction` · `Unknown cost`

- `Contradiction` shows both passages and is always `needs_review`.
- `Unknown cost` never carries an amount.

### Costs
- Currency INR. Common basis: **monthly**.
- Annual ÷ 12. Quarterly ÷ 3. Per-visit / per-unit with no stated frequency → `unknown`.
- GST always separate from base amount. Tax status: `inclusive` · `exclusive` · `not stated`.
- Each cost item is `included` · `excluded` · `optional` · `unknown`.
- Normalisation is Python code, not a model output.

### Scoring
- Criteria and default weights live in config, not code constants scattered around.
- Weights must sum to 100; otherwise normalise and report that normalisation happened.
- Output per vendor: each criterion score, its weight, its contribution, the total, and mandatory failures (separate list).
- Store the weights used with every result.
- Every scoring function has unit tests. Changing scoring without tests is forbidden.

### Evidence references
- Documents are split into segments with stable IDs: `{document_id}:{segment_index}`.
- Each segment stores `page` (PDF) or `section` (DOCX heading path).
- The model cites segment IDs only. Verification code resolves them.

---

## 7. Code rules

### Backend
- Routers are thin: validate input, call a service, return a schema. No business logic in routers.
- Every route depends on the auth dependency. Only `/api/health` is public.
- Firestore paths always start from the user: `users/{uid}/evaluations/{evaluation_id}/...`.
- All Gemini calls go through `app/llm/`. Nothing else imports the Gemini SDK.
- Model output is always schema-enforced (response schema = Pydantic model).
- Temperature ≤ 0.2. Bounded retries: max 2 on invalid output, then a visible error.
- Model names come from config (`GEMINI_EXTRACT_MODEL`, `GEMINI_ANALYSIS_MODEL`).
- Prompts are files in `app/llm/prompts/`, with a version header. Changing a prompt bumps its version.
- Never log document text or full model responses. Log IDs, counts, durations, error types.
- Each pipeline step is its own endpoint and is idempotent (re-run replaces that step's results).
- Editing requirements marks downstream results `stale`.

### Frontend
- Types come only from `lib/types/` (generated). Never hand-write API types.
- All API calls go through `lib/api/`, which attaches the Firebase ID token.
- Use shadcn/ui components and Tailwind tokens. No inline hex colours; colours live in the Tailwind theme.
- Every data view handles four states: loading, empty, error, success.
- Status and risk values render from the exact enum values above. One colour per status, defined once.

### Config and secrets
- All config via environment variables, documented in `.env.example`.
- Never commit secrets, keys, tokens, or real `.env` files.
- Locally `.env`; on Cloud Run, Secret Manager.

### Tests
- `make test` must not call Gemini live. Use recorded fixtures in `tests/fixtures/llm/`.
- Required test coverage: scoring, cost normalisation, quote verification, auth dependency, user scoping.

---

## 8. Forbidden

- Deleting files or folders unless the task explicitly says so.
- Editing anything in `dataset/expected/`.
- Hand-editing `frontend/src/lib/types/`.
- Changing a schema without running `make types` and updating every call site and test mock.
- Calling Gemini outside `app/llm/`.
- Letting a model produce or adjust a score.
- Adding non-Google cloud services, analytics, or telemetry.
- Database migrations, data deletion, or anything touching real cloud resources unless the task explicitly says so.
- Force-pushing, rewriting history, or committing to anything other than the instructed branch.
- Using `rg`. Use `grep` for all searches.
- Guessing when the task is ambiguous. Do the unambiguous part, then list the ambiguity under Open issues.

---

## 9. Before changing a function signature

1. `grep` every call site, including tests and mocks (`monkeypatch.setattr`, `MagicMock`, lambda fakes, fixtures).
2. Update all of them in the same task.
3. List them in the change summary.

---

## 10. After every task (mandatory)

1. Run `make test` (and `make types` if schemas changed). Fix failures before finishing.
2. Update `docs/context/implementation-map.md` — what exists now, where, and its status.
3. Update `docs/context/architecture.md` if flow, services, or data shapes changed.
4. Append to `docs/context/decisions.md` — one dated line per decision: `YYYY-MM-DD — decision — reason`.
5. Commit with message: `P<n>: <short summary>`.
6. Output the change summary below, exactly in this format.

### Change summary format

```
## Change summary — P<n>

### Files
- added: ...
- modified: ...
- deleted: ... (only if instructed)

### Endpoints
- METHOD /api/... — purpose — new | changed | unchanged

### Schemas
- ModelName — new | changed (fields) | unchanged

### Tests
- make test: PASS | FAIL (count passed / failed)
- new tests: ...

### Docs updated
- implementation-map | architecture | decisions

### Expected outcome check
- <expected outcome from the prompt> — MET | NOT MET (why)

### Open issues
- ...
```

---

## 11. Context docs

`docs/context/` is the shared memory between humans, the reviewer, and agents.

- **implementation-map.md** — per component: responsibility, location, status (`done` · `partial` · `stub`), known gaps.
- **architecture.md** — containers, services, pipeline steps, data model, auth flow.
- **decisions.md** — append-only log. Never rewrite past entries; add a superseding entry instead.

Read all three at the start of every task.