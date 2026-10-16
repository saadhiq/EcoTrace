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
| 8 | Screenshots | ☐ | `docs/screenshots/` — have: `step1-login`, `step1-{resident,collector,operator,admin}`, `step1-mobile-resident`, `step2-{onboarding,dashboard,schedule,bags-qr,mobile}` |
| 9 | Gemini classification deep-dive | ☐ | Prompt, schema, accuracy |
| 10 | Performance / benchmark report | ☐ | Latency, cost, classification accuracy |
| 11 | Privacy (opt-in, anonymization) | ☐ | |
| 12 | Impact & roadmap | ☐ | Partner API |

## For judges

Open https://ecotrace-9e406.web.app → **Try a demo account** → pick any role (no password). Accounts are shared; the demo resident always has a household, bags and an upcoming pickup ready (repaired on every demo sign-in, never wiped). Or sign up to go through onboarding yourself.

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
- Full schema: [`docs/DATA_MODEL.md`](DATA_MODEL.md).
- **Collections:**
  - `users/{uid}` — `{name, email, role, createdAt}`; mirrors the role claim.
  - `households/{uid}` — one per resident (id = owner uid, created with `create()` so it is unique); address, zone, opt-in `consent.dataSharing` (default false).
  - `bags/{code}` — human-readable, random, check-digit codes like `ECO-7K3M-Q9`; status lifecycle `issued → scheduled → collected → at_warehouse → processed` with `statusHistory`.
  - `pickups/{id}` — date (tomorrow…+14 days, Colombo time), slot, 1–5 bags, status `requested → assigned → collected → delivered → processed | cancelled` with `statusHistory`.
- **Writes only through the API.** Scheduling validates (date window, bag count, ownership, `issued` status, one pickup per date) and then writes the pickup and all its bags in **one atomic batch**; cancelling returns bags to `issued` in the same batch.
- **Realtime listeners:** the resident dashboard and "My bags" page subscribe with Firestore `onSnapshot` (queries `pickups where residentUid == me order by date` and `bags where ownerUid == me order by issuedAt`, backed by composite indexes in `firestore.indexes.json`). Status changes made by the backend show up live, with no polling; the progress tracker (requested → assigned → collected → delivered → processed) updates in place.
- **Security rules:** clients may only **read their own** `users`, `households`, `bags` and `pickups` docs (matched on `ownerUid` / `residentUid`); no client writes at all. Verified on the live project with real ID tokens (17/17 checks): owner reads and queries → 200; another resident's direct reads and filtered queries, any write, and unauthenticated reads → 403.

### Cloud Run
- FastAPI backend service `ecotrace-api` in `asia-south1`, built from source by Cloud Build (`gcloud run deploy --source`), image stored in Artifact Registry.
- Runs as a dedicated least-privilege service account `ecotrace-backend@ecotrace-9e406.iam.gserviceaccount.com`:
  - `roles/datastore.user` (Firestore document read/write, no admin)
  - `roles/firebaseauth.admin` (set custom claims, manage demo users)
  - custom role `ecotraceTokenSigner` (**only** `iam.serviceAccounts.signBlob`), bound **on itself only**, to sign Firebase custom tokens — narrower than the predefined Token Creator role
- Endpoints so far: `GET /health`, `GET /zones`, `POST /auth/register`, `GET /me`, `POST /auth/demo/{role}`, `POST /households`, `GET|PATCH /households/me`, `GET /bags/mine`, `POST /bags/request-more`, `POST /pickups`, `GET /pickups/mine`, `POST /pickups/{id}/cancel`.
- 92 backend tests (pytest, in-memory fakes) cover every validation rule.
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
| 2 | Resident flow: signBlob-only custom IAM role; households (onboarding), bag QR codes + printable labels, pickup scheduling/cancel with validation and batch writes, live `onSnapshot` tracker, own-data read rules + indexes, demo resident data | ✅ |
