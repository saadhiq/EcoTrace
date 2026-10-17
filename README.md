# EcoTrace

Traceable household waste collection, built for the Google Cloud **AI Builder Cup**.

Residents schedule pickups, collectors scan each bag's QR code, warehouse operators photograph bag contents, and **Gemini** classifies the items. Results are stored per household in **Firestore**, and opt-in, anonymized recommendations are served by an API on **Cloud Run**.

> Status: auth, the **resident flow** (onboarding, bag QR codes, scheduling with a live tracker) and the **collector flow** (accept, scan bags with the phone camera, complete, hand over at the warehouse) and the **warehouse operator flow with Gemini** (photograph a bag → AI item list → human review → processed) and **resident insights** (eco score, points, category breakdown, Gemini tips in English/Sinhala/Tamil, opt-in data sharing), **sustainable-swap recommendations**, the **partner API** and the **admin dashboard** (overview, AI quality, pickups with timelines, people, partners) are live.

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

## Collector flow

1. **Today** — pickups available in my zones plus my route, with a date switcher, the resident's phone and an *Open in Google Maps* directions link. Bag codes are never shown before the scan.
2. **Pickup screen** — scan each bag's QR with the phone camera (or type the code); a checklist ticks off live with a green/red flash. Wrong bags, typos (caught by the code's check character) and repeat scans get clear messages. Demo accounts get a **Simulate scan** button per bag.
3. **Complete**, **Complete with missing bags** (with a reason; unscanned bags go back to the resident) or **Mark missed** (resident not available).
4. **Warehouse handover** — scan every bag from the van; when a pickup's last bag arrives it becomes *delivered*, and the resident's tracker moves **assigned → collected → delivered** live.

| Today (collector) | Scanning on a phone | Resident tracker |
|---|---|---|
| ![Collector today](docs/screenshots/step3-collector-today.png) | ![Scan](docs/screenshots/step3-scan.png) | ![Delivered](docs/screenshots/step3-resident-tracker-delivered.png) |

## Live

- **Web app (Firebase Hosting):** https://ecotrace-9e406.web.app
- **API (Cloud Run):** https://ecotrace-api-frl7lolcea-el.a.run.app — health check: [`/health`](https://ecotrace-api-frl7lolcea-el.a.run.app/health)

## Tech stack

- **Frontend:** Next.js (TypeScript) on Firebase Hosting
- **Backend:** Python FastAPI on Cloud Run
- **Google Cloud:** Firebase Auth, Firestore, Cloud Storage, Vertex AI Gemini (`asia-south1`)

## Warehouse operator + Gemini

1. **Queue** — bags handed over at the warehouse, oldest first (scan or type a code to open one).
2. **Photograph** the bag's contents (phone camera or upload; demo accounts can use a sample photo). Photos are
   resized in the browser and stored in a private Cloud Storage bucket that deletes them after 30 days.
3. **Gemini on Vertex AI** (`gemini-3.5-flash`, asia-south1, structured output) lists every item with a category
   from a fixed taxonomy, material, quantity, recyclability and confidence, plus segregation quality and hazard
   flags — typically in 2–3.5 s. The prompt forbids transcribing personal information and treats any text in the
   photo as a label, never an instruction.
4. **Review** — the operator edits the table (low-confidence rows highlighted), then confirms. Both Gemini's
   answer and the final list are stored, so AI accuracy can be measured. If Gemini is unavailable, the operator
   enters items manually.
5. When a pickup's last bag is confirmed, the resident's tracker reaches **Processed** live.

| Gemini result | After review | Resident tracker |
|---|---|---|
| ![Gemini result](docs/screenshots/step4-results.png) | ![Edited](docs/screenshots/step4-edited.png) | ![Processed](docs/screenshots/step4-resident-processed.png) |

Sample photos: Wikimedia Commons, see [docs/sample-images/CREDITS.md](docs/sample-images/CREDITS.md).

## Resident insights

- **Eco score (0–100)** — a transparent formula, not AI: 50 % sorting quality + 30 % recyclable share + 20 % safe
  hazard disposal, across all processed bags. Shown with its parts and a one-line explanation.
- **Points** — +10 per processed bag, +5 when it's well sorted, +5 when hazardous items were packed separately; recent
  awards listed.
- **What you throw away** — per-category breakdown and an eco-score trend by pickup, updating **live** when the
  warehouse confirms a bag.
- **Pickup history** — tap a processed pickup to see what was found in each bag (no photos).
- **Tips** — Gemini writes 3 personalised tips in **English, සිංහල or தமிழ்** from aggregated stats only; cached until
  the stats change.
- **Privacy & sharing** — opt-in (off by default) with a plain explanation of what would and would never be shared;
  every change is logged.

| Insights | Tips (Sinhala) | Privacy |
|---|---|---|
| ![Insights](docs/screenshots/step5-insights.png) | ![Tips in Sinhala](docs/screenshots/step5-tips-si.png) | ![Consent](docs/screenshots/step5-consent.png) |

## Sustainable swaps & partner API

- **Swaps for residents (with consent):** partner products matched to what the household actually throws away.
  A deterministic step finds candidate products; **Gemini** picks up to 4 **from those candidates only** and explains
  each with the household's own numbers. Hallucinated products are dropped; a deterministic ranking is the fallback.
- **Partner API v1** (`/partner/v1`, `X-API-Key`): anonymised **segments** (rule-based, e.g. *beverage-plastic heavy*),
  the partner's products that fit a segment, and category trends by zone. Only consenting households count, and any
  group smaller than **5 households is suppressed**. Try it in the interactive docs:
  **https://ecotrace-api-frl7lolcea-el.a.run.app/docs** → *Authorize* → *Try it out* (the demo admin's **Partners** page has the demo key and a *Try the partner API* panel).

| Swaps | Partner API (OpenAPI docs) |
|---|---|
| ![Swaps](docs/screenshots/step6a-swaps.png) | ![Segments response](docs/screenshots/step6a-segments-response.png) |

- **Admin dashboard** (`/admin`): KPIs from Firestore `count()` aggregation queries (cached 60 s) with an
  *Include synthetic data* toggle, waste by category and per zone; an **AI quality** panel (how often operators
  correct Gemini, p95 latency, low-confidence items, failures); pickups with a full timeline and reassignment through
  the state machine; staff accounts; partner engagement. The public demo admin is **read-only for accounts and
  partners** (server-enforced).

| Admin overview | AI quality |
|---|---|
| ![Admin overview](docs/screenshots/step6b-overview.png) | ![AI quality](docs/screenshots/step6b-ai-quality.png) |

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
| `GET /collector/pickups?date=` · `GET /collector/pickups/{id}` | collector | Available in my zones + my route (no bag codes) |
| `POST /collector/pickups/{id}/accept` · `/scan` · `/complete` · `/missed` | collector | Accept, scan a bag, complete (full/partial), missed |
| `POST /collector/pickups/{id}/simulate-scan` | demo collector | Scan without a printed label |
| `GET /collector/handover` · `POST /collector/handover/scan` | collector | Bags in my van; hand over at the warehouse |
| `GET /taxonomy` | none | Waste categories, hazard flags, segregation levels |
| `POST /residents/me/tips?lang=en\|si\|ta` | resident | 3 Gemini tips from aggregated stats (cached) |
| `GET /residents/me/pickups/{id}/details` | resident | Items found per bag (no photos) |
| `GET`/`PUT /households/me/consent` | resident | Data-sharing consent + history |
| `GET /residents/me/swaps` · `POST /residents/me/swaps/{sku}/click` | resident (consent) | Personal swaps; anonymous click count |
| `GET /partner/v1/segments` · `/segments/{name}/recommendations` · `/insights?zone=` | partner (`X-API-Key`) | Anonymised segments (K ≥ 5), fitting products, zone trends |
| `GET /operator/queue` · `GET /operator/bags/{code}` | operator | Warehouse queue; bag + draft analysis |
| `POST /operator/bags/{code}/analyze` | operator | 1–3 photos → Gemini structured result (draft) |
| `POST /operator/bags/{code}/confirm` | operator | Final items → bag processed (last bag → pickup processed) |

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
