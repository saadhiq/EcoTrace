# CLAUDE.md — EcoTrace

Guidance for Claude (and humans) working in this repo.

> **FREEZE (submission, 2026-10-17):** no production deploys after submission — no `deploy-backend.sh`,
> `deploy-frontend.sh`, `firebase deploy`, traffic changes, IAM or service-config changes, and no writes to
> production data (seed, backfill, cleanup scripts) — **unless the user explicitly asks for that specific action**.
> Local code changes, tests and docs are fine. Keep the free tier: Cloud Run stays at `min-instances 0`.
> Exceptions so far (each explicitly requested): 2026-10-17 one Hosting-only deploy of the landing page
> (`deploy-frontend.sh` = `firebase deploy --only hosting`), with its live smoke test + `isTest` cleanup; 2026-10-18 `grant_admin.py` for the team's real admin account (shared with judges privately, never in the repo). The freeze is back in force.

## Project

**EcoTrace** is a traceable household waste-collection platform built for the Google Cloud **AI Builder Cup** hackathon.
Mandatory tech: **Firebase, Firestore, Cloud Run, Gemini**. Everything runs on Google Cloud, region **`asia-south1`**.

## Google Cloud resources

| Item | Value |
|---|---|
| Project ID / number | `ecotrace-9e406` / `55962094566` |
| Region | `asia-south1` |
| Cloud Run service | `ecotrace-api` → https://ecotrace-api-frl7lolcea-el.a.run.app |
| Runtime service account | `ecotrace-backend@ecotrace-9e406.iam.gserviceaccount.com` — project roles `roles/datastore.user`, `roles/firebaseauth.admin`; custom role `projects/ecotrace-9e406/roles/ecotraceTokenSigner` (only `iam.serviceAccounts.signBlob`) bound on **itself only** for custom-token signing; `roles/aiplatform.user`; `roles/secretmanager.secretAccessor` on the two secrets `partner-api-key-greencart-lk` / `partner-api-key-ecohome-store` only. Grant new roles per step, least privilege, with user approval. |
| Firestore | `(default)`, Native mode, `asia-south1`; schema + state machine in `docs/DATA_MODEL.md`; rules: clients read only their own `users` / `households` / `bags` / `pickups` (residents) and `routes` (collectors), no client writes |
| Firebase Hosting | https://ecotrace-9e406.web.app (static export from `frontend/out`) |
| Photo bucket | `gs://ecotrace-9e406-bag-photos` (asia-south1, private, public access prevention, lifecycle: delete after 30 days); SA has objectCreator + objectViewer on it only |
| Gemini | `gemini-3.5-flash` on Vertex AI `asia-south1`, `thinking_level=minimal`; SA has `roles/aiplatform.user` |
| Firebase web app | `EcoTrace Web` — `1:55962094566:web:eff857d7171aac9606e427` |

Backend env vars: `ALLOWED_ORIGINS` (comma-separated CORS origins), `GOOGLE_CLOUD_PROJECT`, `DEMO_RATE_LIMIT_PER_MIN` (default 10), `GEMINI_MODEL`, `GEMINI_LOCATION`, `GEMINI_THINKING_LEVEL`, `GEMINI_TIMEOUT_S`, `GEMINI_TIPS_TIMEOUT_S` (default 10), `ANALYZE_RATE_LIMIT_PER_MIN` (default 10), `TIPS_RATE_LIMIT_PER_MIN` (default 10, also used for swap ranking), `PARTNER_RATE_LIMIT_PER_MIN` (default 60), `PHOTO_BUCKET` (all set by `deploy-backend.sh`).
Frontend build-time env: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_FIREBASE_*` (filled by `deploy-frontend.sh`; see `frontend/.env.example`).

## Auth & roles model

- **Firebase custom claim `role`** (`resident | collector | operator | admin`) is the source of truth; `users/{uid}` `{name, email, role, createdAt}` mirrors it. Only the backend writes either.
- Self sign-up → `POST /auth/register` → `resident`. It never changes an existing role. Staff accounts come only from an admin (`POST /admin/staff`, real admins only) or `scripts/seed_demo_users.py`. Make a real admin with `scripts/grant_admin.py <email>` (existing Firebase user).
- Every protected call sends `Authorization: Bearer <Firebase ID token>`. Backend: `get_current_user` (verify), `require_role(Role.X, ...)` / `require_registered` (authorise). Firebase/Firestore are behind `IdentityAdmin` / `UserStore` interfaces (`app/identity.py`, `app/users.py`) so tests use fakes (`tests/fakes.py`).
- Demo accounts: fixed uids `demo-{role}`, no password. `POST /auth/demo/{role}` repairs the user and returns a custom token (frontend: `signInWithCustomToken`). Rate-limited per client IP (last `X-Forwarded-For` entry, in-memory per instance).
- Frontend: `AuthProvider` (`useAuth()`), `RoleGuard` for each dashboard, `dashboardPath(role)` for redirects. Guards are UX only; the backend and Firestore rules enforce access.

## Backend structure & data rules

- `app/models.py` (Pydantic models = Firestore doc shapes), `app/store.py` (`DataStore` interface + `FirestoreDataStore`), `app/services.py` (all business rules, raising `DomainError(status, detail)`), `app/routes/*.py` (thin), `app/deps.py` (`get_store`, `get_clock` — overridden in tests with `FakeDataStore` / `FixedClock`).
- **All status changes go through `app/transitions.py`** (`advance_pickup` / `advance_bag`). Add new transitions there; never set `status` directly.
- **Collectors never read `pickups` from the client** (bag codes would leak). Every collector-side pickup change also writes the `routes/{pickupId}` mirror in the same batch (`collector._commit`, `services.route_stop`).
- Collector logic: `app/collector.py` (views hide codes until scanned); routes: `app/routes/collector.py`. Demo-only endpoints check `is_demo_uid()` on the server.
- **Gemini** lives in `app/ai/classifier.py` (`GeminiClassifier`, system prompt, response schema, `parse_ai_output`, one retry). Never trust model output: always go through `parse_ai_output`. Tests mock the SDK (`tests/test_classifier.py`) or use `FakeClassifier`.
- **Operator flow** in `app/operator.py`: `analyze` writes a server-side DRAFT `wasteRecords/{code}`; `confirm` computes `edited`/`editCount` from that draft (the client never sends `aiResult`). Keep both `aiResult` and `finalItems`. Photos via `app/photos.py` (`GcsPhotoStore`, create-only); taxonomy only in `app/taxonomy.py`.
- **Insights** (`app/insights.py`): stats, eco score and points are pure functions of the household's confirmed `wasteRecords`. Never increment stats: call `rebuild()` and write the result in the same batch as the change (operator confirm does). Ledger ids are `{bagCode}-{reason}` (idempotent). The eco score never comes from Gemini. Repair/backfill: `scripts/backfill_stats.py`.
- **Tips** (`app/ai/tips.py`, `app/residents.py`): Gemini gets ONLY `insights.tips_payload()` (aggregates). Cache in `households/{id}/tips/{lang}` keyed by `statsHash`; fallback tips are never cached. Shared Gemini client/retry lives in `app/ai/gemini.py`.
- **Swaps** (`app/recommendations.py`): stage 1 deterministic candidates (`find_candidates`, direct item-type matches before category matches); stage 2 Gemini picks ONLY from candidates and `validate_picks` drops anything else; deterministic fallback. Gemini gets only `ranking_payload()` (aggregates + candidates). Cache keyed by `statsHash` + `catalogVersion`; deleted on consent withdrawal.
- **Partner API** (`app/partner_api.py`, `app/routes/partner.py`, `/partner/v1`): key auth (`etp.<partner>.<random>`, SHA-256 hash stored, plain key only in Secret Manager), per-key rate limit, consenting households only, **K_MIN = 5** for every reported group. Never return household ids or per-household rows. Segments are rules in `app/segments.py` (bump `SEGMENT_VERSION` if they change).
- **Admin** (`app/admin.py`, `app/routes/admin.py`, `/admin`): every route needs the `admin` claim. **Demo guard:** any route that creates/changes accounts, zones, partners or keys MUST depend on `deny_in_demo` (403 `demo_disabled` for the demo admin) and be added to `PROTECTED` in `tests/test_admin.py`. The demo admin may reassign only demo/synthetic households' pickups (checked in `assign_pickup`) and sees real users' emails masked. Reads (overview, ai-quality, partners) are cached 60 s in `app.state.admin_cache` (`TTLCache`); admin writes call `cache.clear()`. Pickup counts use Firestore `count()` aggregations (`DataStore.count_pickups`, indexes `(status,date)` + `(status,isSynthetic,date)`); zone/category totals come from `stats/summary` (`zone`, `isSynthetic`, `realOnly`). Reassign goes through `transitions.reassign_pickup` + the `routes` mirror. Demo partner keys are read only via `app/secrets.py` (`DEMO_PARTNER_IDS`; any other id → 404 before Secret Manager is called).
- **Gemini endpoints:** classification (photos) is regional only; tips + swaps may retry on `global` after a regional 5xx (`generate_with_retry(..., fallback_client=)`).
- **Never commit API keys** — also not in screenshots (Swagger shows the key in its curl example: mask it).
- **Consent**: every `dataSharing` change (PUT consent or PATCH household) goes through `residents.consent_change()` and logs `consentHistory` in the same batch. Bump `CONSENT_TEXT_VERSION` when the explanation text changes.
- **Synthetic data**: seeded demo history is `isSynthetic: true` (`app/demo_history.py`); exclude it from analytics/benchmarks. `app/demo_partners.py` seeds 50 synthetic households (zones incl. nugegoda/dehiwala/colombo-03/rajagiriya) and `synthetic-collector-b` (users doc only, no login, all zones).
- Demo operator: `ensure_demo_operator_data()` queues one delivered demo pickup (2 bags) only when the warehouse queue is empty.
- **No Firestore transactions (demo scope).** Validate, then write all related docs in **one batch** (`DataStore.commit`). Uniqueness via `create()` (households by uid, bags by code).
- Dates for pickups are Colombo calendar days (`app/clock.py`, fixed UTC+5:30); store `"YYYY-MM-DD"`.
- `statusHistory` entries use `clock.now()` (Firestore forbids `SERVER_TIMESTAMP` inside arrays).
- Zones live only in `app/zones.py` and are served by `GET /zones`; the frontend fetches them.
- Bag codes: `app/bagcodes.py` (`ECO-XXXX-XC`, Luhn mod-N check char).
- Demo resident data: `ensure_demo_resident_data()` in `app/demo.py` runs on every `POST /auth/demo/resident` and in the seed script; it only adds, never deletes.
- Demo collector: `ensure_demo_collector_data()` sets its zones and, only when no requested pickup exists today in those zones, creates **one** for today from the demo resident with 2 fresh bags (`demo_override` skips the resident date rules).
- When adding a client query, add a matching composite index to `firestore.indexes.json` if it filters + orders on different fields, and make sure the rules allow it.

## Frontend data conventions

- **Writes** go through `src/lib/*` API helpers (`apiFetch` with the ID token). **Live reads** use Firestore `onSnapshot` hooks in `src/lib/liveData.ts`, always filtered on the caller's uid so the rules allow them.
- Resident pages wrap content in `ResidentPage` (guard + household load + onboarding); collector pages in `CollectorPage`; operator pages in `OperatorPage`; admin pages in `AdminPage` (guard, sub-nav, demo banner; `useAdminData` for fetch state, `Tile` for KPIs).
- Query-param pages (static export): call `useSearchParams()` inside a `<Suspense>` boundary (e.g. `/collector/pickup?id=`).
- QR scanning: `components/collector/ScanPanel.tsx` (`@yudiel/react-qr-scanner`). Its zxing wasm is self-hosted at `/vendor/zxing_reader.wasm`, copied from node_modules by `npm run build`/`dev` (`scripts/copy-zxing-wasm.mjs`, git-ignored). Keep camera constraints soft (`ideal` only): the library's defaults require ≥640px height and fail on 480p cameras (`overconstrained`).
- Effects that fetch must set state in the promise callback (lint rule `react-hooks/set-state-in-effect`).
- **Charts** (resident insights): follow the `dataviz` skill. Category colors are the validated categorical palette in `--cat-*` (light + dark), shown in the FIXED order of `CATEGORY_ORDER` (lib/insights.ts) — never sorted by value, never cycled, zeros kept. Text in text tokens; one axis; hover tooltips; a table view for the trend. Re-run `validate_palette.js` if you change a category color.
- Insights read live via `useHouseholdStats` / `useRecentPoints` (onSnapshot). Sinhala/Tamil text must carry `lang="si"|"ta"` (Noto fonts via next/font).
- Operator pages wrap content in `OperatorPage` (guard + taxonomy + zone names). Photos are resized with `lib/images.ts` before upload; uploads use `apiFetch(..., { form })`. Category colors are `--cat-*` tokens (`CategoryChip`). Demo sample photos live in `public/samples/` (copies of `docs/sample-images/`, see its CREDITS.md).
- **Static export + Hosting:** `npm run build` runs `scripts/flatten-rsc.mjs` (postbuild), which copies Next.js 16's nested route payloads (`__next.a/b.txt`) to the dotted names the client requests (`__next.a.b.txt`). Without it every client navigation 404s and falls back to a full page load.
- **Landing page** (`/`, `components/landing/Landing.tsx`, server `app/page.tsx` holds the metadata): public, no redirect; signed-in users get "Go to my dashboard". One-click demo sign-in lives ONLY in `components/auth/DemoSignIn.tsx` (used by `/` and `/login`); don't duplicate it. No invented stats or testimonials on it.
- Map API error `detail` codes to friendly text (`residentErrorMessage`, `adminErrorMessage`; `demo_disabled` → "Disabled in the public demo.").
- **API keys in the admin UI:** masked by default (`maskKey`); *Copy* never renders the key. Screenshots must never show a revealed key.

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
5. **Production traffic must never move to a test revision.** Failure/experiment tests deploy a separate revision with `--no-traffic --tag <name>` and are called **only via the tag URL** (`https://<name>---<service-url>`). **Never** run `gcloud run services update-traffic --to-latest` (or any "to latest" shortcut): after a `--no-traffic` deploy the latest revision *is* the test revision. Clean up by removing the tag and deleting the tagged revision; Cloud Run refuses to delete the newest revision, so if the test revision is still the newest, leave it untagged at 0% until the next normal deploy creates a newer one, then delete it. `deploy-backend.sh` verifies that the revision it just created serves 100% of traffic and fails loudly otherwise; fix with an explicit `--to-revisions <revision>=100`.

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
backend/.venv/Scripts/python scripts/seed_demo_users.py   # create/repair the 4 demo users + demo data incl. synthetic history (idempotent)
backend/.venv/Scripts/python scripts/backfill_stats.py    # rebuild every household's stats + points ledger
# Seed also creates demo partners (keys -> Secret Manager `partner-api-key-<id>`), 30 synthetic households,
# and turns the demo resident's consent on. Read a demo key: gcloud secrets versions access latest --secret=partner-api-key-greencart-lk
```

Gemini failure-path test without touching production (see rule 5): `EXTRA_DEPLOY_FLAGS="--tag failtest --no-traffic" GEMINI_TIMEOUT_S=0.001 ./scripts/deploy-backend.sh`, call `https://failtest---<service-url>` only, then `gcloud run services update-traffic ecotrace-api --region asia-south1 --remove-tags failtest` and delete the revision once it is no longer the newest.

Local seeding uses your ADC (`gcloud auth application-default login`, quota project `ecotrace-9e406`).
POSTs to Cloud Run must carry a body/Content-Length (Google's front end returns 411 otherwise); `apiFetch` always sends JSON.

The frontend is a static export: no SSR, no API routes, no server-only Next.js features.
