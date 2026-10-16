# EcoTrace — Submission Tracker

Google Cloud **AI Builder Cup**. Tick items as they are completed.

## Submission items

- [ ] Public GitHub repo — https://github.com/saadhiq/EcoTrace
- [x] Deployed link (must stay up during judging): https://ecotrace-9e406.web.app (API: https://ecotrace-api-frl7lolcea-el.a.run.app)
- [ ] Demo video (3–4 min): _TBD_
- [ ] Pitch deck: _TBD_
- [ ] Performance / benchmark report (in deck + `docs/`)
- [ ] README with setup instructions and live link

## Pitch deck slides

| # | Slide | Status | Source / notes |
|---|---|---|---|
| 1 | Title & team | ☐ | |
| 2 | Problem | ☐ | |
| 3 | Solution — EcoTrace overview | ☐ | |
| 4 | Users & roles | ☐ | Resident, collector, warehouse operator, admin, partner |
| 5 | Process flow | ☐ | Schedule → collect (QR) → photograph → Gemini classify → store → recommend |
| 6 | Architecture diagram | ☐ | Firebase Hosting, Auth, Firestore, Storage, Cloud Run, Vertex AI Gemini, Secret Manager |
| 7 | How we use Google Cloud | ☐ | From the section below |
| 8 | Screenshots | ☐ | `docs/screenshots/` — have: `step1-login`, `step1-{resident,collector,operator,admin}`, `step1-mobile-resident` |
| 9 | Gemini classification deep-dive | ☐ | Prompt, schema, accuracy |
| 10 | Performance / benchmark report | ☐ | Latency, cost, classification accuracy |
| 11 | Privacy (opt-in, anonymization) | ☐ | |
| 12 | Impact & roadmap | ☐ | Partner API |

## For judges

Open https://ecotrace-9e406.web.app → **Try a demo account** → pick any role (no password). Demo accounts reset on every sign-in.

## Demo video checklist (3–4 min)

- [ ] Script written
- [ ] Resident schedules pickup
- [ ] Collector scans QR
- [ ] Operator photographs bag → Gemini classification
- [ ] Household history + recommendations
- [ ] Architecture recap
- [ ] Recorded, edited, uploaded

## How we use Firebase, Firestore, Cloud Run and Gemini

_Fill in as each piece is built._

### Firebase (Hosting, Auth)
- **Hosting:** the Next.js frontend is built as a static export (`output: 'export'`) and served from Firebase Hosting at https://ecotrace-9e406.web.app. Deployed with `scripts/deploy-frontend.sh`.
- **Auth:** Firebase Authentication (email/password + custom tokens) via the Firebase JS SDK.
  - **Roles as custom claims** (`role`: resident | collector | operator | admin) are the source of truth. The backend verifies every ID token with the Firebase Admin SDK and enforces roles with a `require_role(...)` FastAPI dependency.
  - **Self sign-up → resident only.** `POST /auth/register` sets the `resident` claim the first time and never changes an existing role (staff can't be downgraded, nobody can self-promote). The client auto-retries registration once if `/me` says `not_registered`.
  - **One-click demo for judges:** `POST /auth/demo/{role}` repairs a passwordless demo user (recreates it if deleted, resets its claim and profile) and returns a **Firebase custom token**; the browser signs in with `signInWithCustomToken`. Rate-limited per client IP. Custom tokens are signed with IAM `signBlob` as the Cloud Run service account — no key files.
  - Client-side route guards send each user to their role's dashboard (`/resident`, `/collector`, `/operator`, `/admin`).

### Firestore
- Native-mode database `(default)` in `asia-south1`.
- **`users/{uid}`** — `{name, email, role, createdAt}`; mirrors the role claim for querying/display. Written only by the backend (Admin SDK).
- **Security rules:** a signed-in user can read only their own `users/{uid}`; all other client reads and all client writes are denied (verified with live REST calls: own doc 200, other user's doc / list / write / unauthenticated → 403).

### Cloud Run
- FastAPI backend service `ecotrace-api` in `asia-south1`, built from source by Cloud Build (`gcloud run deploy --source`), image stored in Artifact Registry.
- Runs as a dedicated least-privilege service account `ecotrace-backend@ecotrace-9e406.iam.gserviceaccount.com`:
  - `roles/datastore.user` (Firestore document read/write, no admin)
  - `roles/firebaseauth.admin` (set custom claims, manage demo users)
  - `roles/iam.serviceAccountTokenCreator` **on itself only** (sign custom tokens via `signBlob`)
- Endpoints so far: `GET /health`, `POST /auth/register`, `GET /me`, `POST /auth/demo/{role}`.
- Scales to zero (`min-instances 0`); CORS restricted to localhost + Firebase Hosting domains via the `ALLOWED_ORIGINS` env var.
- The home page calls `/health` and shows "API: connected" (`docs/screenshots/00-home-api-connected.png`).

### Gemini (Vertex AI)
- _TBD_

### Other Google Cloud (Cloud Storage, Secret Manager)
- _TBD_

## Step log

| Step | Description | Status |
|---|---|---|
| 0 | Monorepo scaffold: Next.js placeholder, FastAPI `/health` + Dockerfile, docs | ✅ |
| 0b | First deployment: APIs enabled, runtime SA, Firestore (deny-all rules), Cloud Run `ecotrace-api` with CORS, Hosting static export showing API status, deploy scripts | ✅ |
| 1 | Auth & roles: Firebase Auth, custom-claim roles, `/auth/register`, `/me`, one-click demo accounts via custom tokens, role-guarded dashboards, design system, own-doc Firestore rules | ✅ |
