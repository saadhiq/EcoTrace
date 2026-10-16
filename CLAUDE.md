# CLAUDE.md — EcoTrace

Guidance for Claude (and humans) working in this repo.

## Project

**EcoTrace** is a traceable household waste-collection platform built for the Google Cloud **AI Builder Cup** hackathon.
Mandatory tech: **Firebase, Firestore, Cloud Run, Gemini**. Everything runs on Google Cloud, region **`asia-south1`**.

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
