# EcoTrace

Traceable household waste collection, built for the Google Cloud **AI Builder Cup**.

Residents schedule pickups, collectors scan each bag's QR code, warehouse operators photograph bag contents, and **Gemini** classifies the items. Results are stored per household in **Firestore**, and opt-in, anonymized recommendations are served by an API on **Cloud Run**.

> Status: authentication and role dashboards are live; waste-collection features are next.

**Try it:** open the web app and click **Try a demo account** — one click signs you in as a resident, collector, warehouse operator or admin (no password).

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

![Login page](docs/screenshots/step1-login.png)

## Repository layout

```
frontend/   Next.js app
backend/    FastAPI service + Dockerfile
docs/       Submission tracker, architecture, benchmarks, screenshots
scripts/    One-command deploy scripts
firebase.json, .firebaserc, firestore.rules   Firebase Hosting + Firestore config
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
firebase deploy --only firestore:rules
backend/.venv/Scripts/python scripts/seed_demo_users.py   # create/repair demo users (idempotent)
```

## Secrets

No secrets are committed. Local config goes in `.env` (git-ignored; see `.env.example`); deployed services use Secret Manager.
