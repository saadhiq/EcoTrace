# EcoTrace

Traceable household waste collection, built for the Google Cloud **AI Builder Cup**.

Residents schedule pickups, collectors scan each bag's QR code, warehouse operators photograph bag contents, and **Gemini** classifies the items. Results are stored per household in **Firestore**, and opt-in, anonymized recommendations are served by an API on **Cloud Run**.

> Status: auth, role dashboards and the **resident flow** (household onboarding, bag QR codes, pickup scheduling with a live tracker) are live. Collector, warehouse and Gemini steps are next.

**Try it:** open the web app and click **Try a demo account** — one click signs you in as a resident, collector, warehouse operator or admin (no password). The demo resident already has a household, bags and an upcoming pickup.

## Resident flow

1. **Onboarding** — a new resident enters household name, phone, address and zone; 5 bags with unique QR codes are issued.
2. **My bags** — each bag shows its QR code (generated in the browser) and status; print an A4 label sheet; request 5 more (max 20 unused).
3. **Schedule a pickup** — date (tomorrow…14 days ahead), morning/afternoon, 1–5 ready bags, notes.
4. **My pickups** — live progress tracker *requested → assigned → collected → delivered → processed*, updated in real time with Firestore listeners; cancel while requested/assigned (bags return to ready).

| Dashboard | Bag QR codes |
|---|---|
| ![Resident dashboard](docs/screenshots/step2-dashboard.png) | ![Bag QR codes](docs/screenshots/step2-bags-qr.png) |

Data model and rules: [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Live

- **Web app (Firebase Hosting):** https://ecotrace-9e406.web.app
- **API (Cloud Run):** https://ecotrace-api-frl7lolcea-el.a.run.app — health check: [`/health`](https://ecotrace-api-frl7lolcea-el.a.run.app/health)

## Tech stack

- **Frontend:** Next.js (TypeScript) on Firebase Hosting
- **Backend:** Python FastAPI on Cloud Run
- **Google Cloud:** Firebase Auth, Firestore, Cloud Storage, Vertex AI Gemini, Secret Manager (`asia-south1`)

## Roles & auth

- Firebase Authentication; the user's **role is a Firebase custom claim** (`resident`, `collector`, `operator`, `admin`), mirrored in Firestore `users/{uid}`.
- Anyone who signs up is a resident. Staff accounts are created by an admin or the seed script.
- The FastAPI backend verifies every Firebase ID token with the Admin SDK and checks roles per endpoint.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness |
| `POST /auth/register` | ID token | First-time sign-up → resident (never changes an existing role) |
| `GET /me` | ID token | Profile + role |
| `POST /auth/demo/{role}` | none (rate-limited) | Repair demo user, return a Firebase custom token |
| `GET /zones` | none | Service zones |
| `POST /households` · `GET`/`PATCH /households/me` | resident | Onboarding + 5 starter bags; view/update household and consent |
| `GET /bags/mine` · `POST /bags/request-more` | resident | List bags; issue 5 more (max 20 unused) |
| `POST /pickups` · `GET /pickups/mine` · `POST /pickups/{id}/cancel` | resident | Schedule (validated), list, cancel |

![Login page](docs/screenshots/step1-login.png)

## Repository layout

```
frontend/   Next.js app
backend/    FastAPI service + Dockerfile
docs/       Submission tracker, data model, screenshots
scripts/    Deploy scripts + demo seed script
firebase.json, .firebaserc, firestore.rules, firestore.indexes.json   Firebase Hosting + Firestore config
```

## Run locally

**Frontend**

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000
```

**Backend**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080   # http://localhost:8080/health
pytest
```

**Backend via Docker**

```bash
cd backend
docker build -t ecotrace-backend .
docker run -p 8080:8080 ecotrace-backend
```

For local frontend dev against a local backend, copy `frontend/.env.example` to `frontend/.env.local` (fill in the Firebase web config from the Firebase console), and run the backend with `ALLOWED_ORIGINS=http://localhost:3000` and `GOOGLE_CLOUD_PROJECT=ecotrace-9e406` using your ADC (`gcloud auth application-default login`).

## Deploy

Prerequisites: `gcloud` and `firebase` CLIs, logged in (`gcloud auth login`, `firebase login`) with access to project `ecotrace-9e406`. Run from Git Bash (or any bash):

```bash
./scripts/deploy-backend.sh    # Cloud Build -> Cloud Run service "ecotrace-api"
./scripts/deploy-frontend.sh   # static export -> Firebase Hosting (API URL read from Cloud Run)
firebase deploy --only firestore   # security rules + composite indexes
backend/.venv/Scripts/python scripts/seed_demo_users.py   # create/repair demo users + demo resident data (idempotent)
```

## Secrets

No secrets are committed. Local config goes in `.env` (git-ignored; see `.env.example`); deployed services use Secret Manager.
