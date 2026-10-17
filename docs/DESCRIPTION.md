# EcoTrace — project description

**EcoTrace** makes household waste traceable from the doorstep to the recycler. Residents schedule pickups for
QR-coded bags; collectors scan every bag on their phone; at the warehouse an operator photographs each bag and
**Gemini** lists what is inside. Every household then gets an eco score, points and practical tips in English,
Sinhala or Tamil. With explicit consent, it also gets sustainable product swaps, and partners get anonymised segments.

**How we use Google Cloud** (all in `asia-south1`):

- **Firebase:** Hosting serves the Next.js app. Firebase Auth signs users in, with the user's role
  (resident, collector, operator, admin) stored as a custom claim. One-click demo accounts use custom tokens.
- **Firestore:** households, bags, pickups, waste records and per-household stats. Browsers read their own documents
  live with `onSnapshot` (security rules allow only their own data), so trackers and scores update in real time. The
  admin dashboard uses `count()` aggregation queries.
- **Cloud Run:** a FastAPI service is the only writer. It verifies Firebase ID tokens, runs one state machine for
  every pickup and bag change, and writes each change in one batch. It also serves the admin API and the Partner API
  (API keys hashed, demo keys in Secret Manager, groups under 5 households suppressed).
- **Gemini (Vertex AI, `gemini-3.5-flash`):** classifies bag photos into a fixed taxonomy with structured output,
  plus hazard flags and sorting quality. An operator reviews every result, and the admin AI-quality panel measures
  how often they correct it. Gemini also writes multilingual tips from aggregates only, and ranks swaps chosen only
  from a validated partner catalog.
