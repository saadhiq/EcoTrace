# EcoTrace — Submission Tracker

Google Cloud **AI Builder Cup**. Tick items as they are completed.

## Submission items

- [ ] Public GitHub repo — https://github.com/saadhiq/EcoTrace
- [ ] Deployed link (must stay up during judging): _TBD_
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
- _TBD_

### Firestore
- _TBD_

### Cloud Run
- FastAPI backend containerised (`backend/Dockerfile`), listens on `$PORT`. _Not yet deployed._

### Gemini (Vertex AI)
- _TBD_

### Other Google Cloud (Cloud Storage, Secret Manager)
- _TBD_

## Step log

| Step | Description | Status |
|---|---|---|
| 0 | Monorepo scaffold: Next.js placeholder, FastAPI `/health` + Dockerfile, docs | ✅ |
