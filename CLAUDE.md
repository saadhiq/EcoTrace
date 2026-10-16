# CLAUDE.md — EcoTrace

Guidance for Claude (and humans) working in this repo.

## Project

**EcoTrace** is a traceable household waste-collection platform built for the Google Cloud **AI Builder Cup** hackathon.
Mandatory tech: **Firebase, Firestore, Cloud Run, Gemini**. Everything runs on Google Cloud, region **`asia-south1`**.

## Google Cloud resources

| Item | Value |
|---|---|
| Project ID / number | `ecotrace-9e406` / `55962094566` |
| Region | `asia-south1` |
| Cloud Run service | `ecotrace-api` → https://ecotrace-api-frl7lolcea-el.a.run.app |
| Runtime service account | `ecotrace-backend@ecotrace-9e406.iam.gserviceaccount.com` — project roles `roles/datastore.user`, `roles/firebaseauth.admin`; custom role `projects/ecotrace-9e406/roles/ecotraceTokenSigner` (only `iam.serviceAccounts.signBlob`) bound on **itself only** for custom-token signing. Grant new roles per step, least privilege, with user approval. |
| Firestore | `(default)`, Native mode, `asia-south1`; schema in `docs/DATA_MODEL.md`; rules: clients read only their own `users` / `households` / `bags` / `pickups`, no client writes |
| Firebase Hosting | https://ecotrace-9e406.web.app (static export from `frontend/out`) |
| Firebase web app | `EcoTrace Web` — `1:55962094566:web:eff857d7171aac9606e427` |

Backend env vars: `ALLOWED_ORIGINS` (comma-separated CORS origins), `GOOGLE_CLOUD_PROJECT`, `DEMO_RATE_LIMIT_PER_MIN` (default 10).
Frontend build-time env: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_FIREBASE_*` (filled by `deploy-frontend.sh`; see `frontend/.env.example`).

## Auth & roles model

- **Firebase custom claim `role`** (`resident | collector | operator | admin`) is the source of truth; `users/{uid}` `{name, email, role, createdAt}` mirrors it. Only the backend writes either.
- Self sign-up → `POST /auth/register` → `resident`. It never changes an existing role. Staff accounts come only from an admin (later step) or `scripts/seed_demo_users.py`.
- Every protected call sends `Authorization: Bearer <Firebase ID token>`. Backend: `get_current_user` (verify), `require_role(Role.X, ...)` / `require_registered` (authorise). Firebase/Firestore are behind `IdentityAdmin` / `UserStore` interfaces (`app/identity.py`, `app/users.py`) so tests use fakes (`tests/fakes.py`).
- Demo accounts: fixed uids `demo-{role}`, no password. `POST /auth/demo/{role}` repairs the user and returns a custom token (frontend: `signInWithCustomToken`). Rate-limited per client IP (last `X-Forwarded-For` entry, in-memory per instance).
- Frontend: `AuthProvider` (`useAuth()`), `RoleGuard` for each dashboard, `dashboardPath(role)` for redirects. Guards are UX only; the backend and Firestore rules enforce access.

## Backend structure & data rules

- `app/models.py` (Pydantic models = Firestore doc shapes), `app/store.py` (`DataStore` interface + `FirestoreDataStore`), `app/services.py` (all business rules, raising `DomainError(status, detail)`), `app/routes/*.py` (thin), `app/deps.py` (`get_store`, `get_clock` — overridden in tests with `FakeDataStore` / `FixedClock`).
- **No Firestore transactions (demo scope).** Validate, then write all related docs in **one batch** (`DataStore.commit`). Uniqueness via `create()` (households by uid, bags by code).
- Dates for pickups are Colombo calendar days (`app/clock.py`, fixed UTC+5:30); store `"YYYY-MM-DD"`.
- `statusHistory` entries use `clock.now()` (Firestore forbids `SERVER_TIMESTAMP` inside arrays).
- Zones live only in `app/zones.py` and are served by `GET /zones`; the frontend fetches them.
- Bag codes: `app/bagcodes.py` (`ECO-XXXX-XC`, Luhn mod-N check char).
- Demo resident data: `ensure_demo_resident_data()` in `app/demo.py` runs on every `POST /auth/demo/resident` and in the seed script; it only adds, never deletes.
- When adding a client query, add a matching composite index to `firestore.indexes.json` if it filters + orders on different fields, and make sure the rules allow it.

## Frontend data conventions

- **Writes** go through `src/lib/*` API helpers (`apiFetch` with the ID token). **Live reads** use Firestore `onSnapshot` hooks in `src/lib/liveData.ts`, always filtered on the caller's uid so the rules allow them.
- Resident pages wrap content in `ResidentPage` (guard + household load + onboarding); other roles use `DashboardPage`.
- Map API error `detail` codes to friendly text (`residentErrorMessage`).

## Frontend UI conventions

- Design tokens (colors incl. per-role accents, spacing, radius, shadows, type) live in `src/app/globals.css`, with dark mode. Never hardcode colors.
- Shared components in `src/components/ui/` (`Button`, `Card`, `Field`, `SelectField`, `TextareaField`, `Alert`, `Notice`, `EmptyState`, `RoleBadge`, `StatusBadge`, `ProgressTracker`, `QrCode`, `Spinner`, `AppShell` (with optional sub-nav), `Logo`, ...). Build new screens from these.
- Plain CSS modules, mobile-first; no horizontal scroll at 390px. Every list has loading, empty and error states.
- Print: `data-print="hide"` hides elements when printing (app chrome uses it).
- Add `data-testid` hooks for anything the browser checks need (CSS-module class names are hashed in production).

## Roles

| Role | What they do |
|---|---|
| Resident | Registers a household, schedules pickups, views their waste history, opts in/out of recommendations |
| Collector | Sees assigned pickups, scans the bag QR code, marks the bag collected |
| Warehouse operator | Scans the bag at the warehouse, photographs its contents for classification |
| Admin | Manages users/roles, zones, collectors; views aggregate stats |
| Partner (later) | Consumes the anonymized recommendation API (server-to-server, API key) |

## Core flow

1. Resident schedules a pickup → pickup + bag (with QR code) created in Firestore.
2. Collector scans the bag QR → bag status `collected`.
3. Warehouse operator photographs bag contents → image uploaded to Cloud Storage.
4. Backend sends image to **Gemini (Vertex AI)** → structured item classification.
5. Classification stored per household in Firestore.
6. Recommendations (opt-in, anonymized) served by the Cloud Run API.

## Architecture

```
 Browser (Next.js on Firebase Hosting)
   │  Firebase Auth (ID token, role via custom claims)
   ├──► Firestore (direct reads/writes guarded by security rules)
   ├──► Cloud Storage (bag photos)
   └──► Cloud Run: FastAPI backend  (verifies Firebase ID token)
            ├──► Vertex AI Gemini (image classification, recommendations)
            ├──► Firestore / Cloud Storage (Admin SDK)
            └──► Secret Manager (API keys, partner keys)
```

## Stack

- **Frontend:** Next.js (TypeScript, App Router, `src/`), hosted on Firebase Hosting.
- **Backend:** Python 3.13, FastAPI, Uvicorn, containerised for Cloud Run.
- **Auth:** Firebase Auth; roles as custom claims.
- **Data:** Firestore (native mode), Cloud Storage.
- **AI:** Gemini via Vertex AI (`google-genai` SDK, Vertex mode).
- **Secrets:** Secret Manager in cloud; local `.env` files (git-ignored).

## Folder structure

```
/frontend          Next.js app
/backend           FastAPI service (app/, tests/, Dockerfile)
/docs              Submission docs, architecture, benchmarks
/docs/screenshots  Screenshots for the deck / README
/scripts           deploy-backend.sh, deploy-frontend.sh, seed_demo_users.py
firebase.json      Hosting (frontend/out) + Firestore rules/indexes config
.firebaserc        Default Firebase project
firestore.rules    Firestore security rules
CLAUDE.md          This file
README.md          Public project overview
```

## Conventions

- **Frontend:** TypeScript strict; ESLint must pass (`npm run lint`); build must pass (`npm run build`). Import alias `@/*` → `src/*`.
- **Backend:** type hints everywhere; Pydantic models for request/response; `ruff check .` and `pytest` must pass. Routes are thin; logic lives in modules under `app/`.
- **Config:** read from environment variables. Commit only `.env.example` files with placeholder values.
- **Commits:** Conventional Commits, scoped — e.g. `feat(backend): add /health`, `chore(frontend): ...`, `docs: ...`.
- **Docs:** after each step, update `docs/SUBMISSION.md` (step log + "How we use…" section) where relevant.

## Rules (must follow)

1. **One small step at a time.** Each step is scoped by the user; propose a plan first when asked.
2. **Never build beyond the current step.** No speculative features, auth, deploys, or dependencies the step didn't ask for.
3. **Never commit secrets.** Use Secret Manager in the cloud and `.env` (excluded by `.gitignore`) locally. No keys, service-account JSON, or tokens in code, docs, or commit history.
4. **Commit after each working step** — only once it builds/tests pass locally.

## Local commands

```bash
# Frontend
cd frontend && npm install && npm run dev        # http://localhost:3000

# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate    # (Windows) or source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080         # GET http://localhost:8080/health
pytest && ruff check .
docker build -t ecotrace-backend . && docker run -p 8080:8080 ecotrace-backend
```

## Deploy commands (bash / Git Bash, from repo root)

```bash
./scripts/deploy-backend.sh              # gcloud run deploy --source backend -> ecotrace-api
./scripts/deploy-frontend.sh             # build static export with NEXT_PUBLIC_API_URL -> Firebase Hosting
firebase deploy --only firestore         # Firestore security rules + composite indexes
backend/.venv/Scripts/python scripts/seed_demo_users.py   # create/repair the 4 demo users + demo resident data (idempotent)
```

Local seeding uses your ADC (`gcloud auth application-default login`, quota project `ecotrace-9e406`).
POSTs to Cloud Run must carry a body/Content-Length (Google's front end returns 411 otherwise); `apiFetch` always sends JSON.

The frontend is a static export: no SSR, no API routes, no server-only Next.js features.
