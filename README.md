# EcoTrace

Traceable household waste collection, built for the Google Cloud **AI Builder Cup**.

Residents schedule pickups, collectors scan each bag's QR code, warehouse operators photograph bag contents, and **Gemini** classifies the items. Results are stored per household in **Firestore**, and opt-in, anonymized recommendations are served by an API on **Cloud Run**.

> Status: early scaffold — no features yet.

## Tech stack

- **Frontend:** Next.js (TypeScript) on Firebase Hosting
- **Backend:** Python FastAPI on Cloud Run
- **Google Cloud:** Firebase Auth, Firestore, Cloud Storage, Vertex AI Gemini, Secret Manager (`asia-south1`)

## Repository layout

```
frontend/   Next.js app
backend/    FastAPI service + Dockerfile
docs/       Submission tracker, architecture, benchmarks, screenshots
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

## Secrets

No secrets are committed. Local config goes in `.env` (git-ignored; see `.env.example`); deployed services use Secret Manager.
