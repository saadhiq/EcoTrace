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
| 8 | Screenshots | ☐ | `docs/screenshots/` |
| 9 | Gemini classification deep-dive | ☐ | Prompt, schema, accuracy |
| 10 | Performance / benchmark report | ☐ | Latency, cost, classification accuracy |
| 11 | Privacy (opt-in, anonymization) | ☐ | |
| 12 | Impact & roadmap | ☐ | Partner API |

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
- **Auth:** _TBD_

### Firestore
- Native-mode database `(default)` in `asia-south1`.
- Security rules (`firestore.rules`) currently **deny all client access**; per-role rules come with auth.

### Cloud Run
- FastAPI backend service `ecotrace-api` in `asia-south1`, built from source by Cloud Build (`gcloud run deploy --source`), image stored in Artifact Registry.
- Runs as a dedicated least-privilege service account `ecotrace-backend@ecotrace-9e406.iam.gserviceaccount.com` (no project roles yet).
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
