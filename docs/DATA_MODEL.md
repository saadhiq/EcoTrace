# EcoTrace — Firestore data model

Database: `(default)`, Native mode, `asia-south1`.
**All writes go through the backend** (FastAPI + Admin SDK). Clients only *read*, and only their own documents (see [Security rules](#security-rules)).

Timestamps are Firestore timestamps (UTC). Pickup dates are calendar days in **Asia/Colombo** (UTC+5:30), stored as `"YYYY-MM-DD"` strings.

## Collections

### `users/{uid}`
Profile mirror of the Firebase Auth user. The **custom claim `role` is the source of truth**; this doc mirrors it for display.

| Field | Type | Notes |
|---|---|---|
| `name` | string | |
| `email` | string \| null | |
| `role` | `resident` \| `collector` \| `operator` \| `admin` | |
| `createdAt` | timestamp | set once |

### `households/{id}`
One per resident. **The document id is the owner's uid**, which makes "one household per resident" atomic via `create()` (fails if the doc exists). A separate anonymised id will be used for the partner API later.

| Field | Type | Notes |
|---|---|---|
| `ownerUid` | string | used by security rules |
| `name` | string | 1–80 chars |
| `phone` | string | `^\+?[0-9][0-9 \-]{6,18}$` |
| `addressLine` | string | 1–200 chars |
| `zone` | string | one of the zone ids below |
| `lat`, `lng` | number \| null | optional |
| `consent` | `{ dataSharing: bool, updatedAt: timestamp }` | `dataSharing` defaults to **false** (opt-in) |
| `createdAt` | timestamp | |

**Zones** (defined once in `backend/app/zones.py`, served at `GET /zones`):
`colombo-03` Kollupitiya · `colombo-05` Havelock Town · `colombo-07` Cinnamon Gardens · `dehiwala` Dehiwala–Mount Lavinia · `nugegoda` Nugegoda · `rajagiriya` Rajagiriya.

### `bags/{code}`
The document id is the bag code, e.g. **`ECO-7K3M-Q9`**:
- `ECO-` + 4 chars + `-` + 1 char + **1 check char**
- 5 random chars (Python `secrets`) from `23456789ABCDEFGHJKMNPQRSTVWXYZ` (no 0/O, 1/I/L, U) → ~24 million codes, non-sequential
- Check char: Luhn mod-N — catches every single-character typo and ~98% of adjacent swaps
- Uniqueness: created with `create()`; a collision retries with new codes

| Field | Type | Notes |
|---|---|---|
| `householdId` | string | |
| `ownerUid` | string | denormalised for security rules |
| `status` | `issued` → `scheduled` → `collected` → `at_warehouse` → `processed` | `issued` = unused, ready for a pickup |
| `pickupId` | string \| null | set while `scheduled` |
| `issuedAt` | timestamp | |
| `statusHistory` | `[{ status, at, by }]` | append-only; `by` = uid or `seed` |

Issuing: 5 bags on household creation; `POST /bags/request-more` adds up to 5, never exceeding **20 unused** (`issued`) bags.

### `pickups/{id}`
Auto id.

| Field | Type | Notes |
|---|---|---|
| `householdId` | string | |
| `residentUid` | string | used by security rules |
| `zone` | string | copied from the household (for collector routing later) |
| `date` | `"YYYY-MM-DD"` | tomorrow … +14 days (Colombo) |
| `timeSlot` | `morning` \| `afternoon` | |
| `bagCodes` | string[] | 1–5, unique, owned by the household, all `issued` |
| `notes` | string | ≤ 280 chars |
| `status` | `requested` → `assigned` → `collected` → `delivered` → `processed`, or `cancelled` | |
| `collectorUid` | string \| null | null until assignment (later step) |
| `statusHistory` | `[{ status, at, by }]` | append-only |
| `createdAt` | timestamp | |

## Rules enforced by the API

| Rule | Error |
|---|---|
| Date from tomorrow to 14 days ahead (Colombo time) | 422 `date_out_of_range` |
| 1–5 bags, no duplicates | 422 `invalid_bag_count` / `duplicate_bags` |
| Every bag belongs to the household (unknown codes give the same error, so codes can't be probed) | 422 `bag_not_owned` |
| Every bag is `issued` (not already in a pickup) | 409 `bag_not_available` |
| At most one non-cancelled pickup per household per date | 409 `pickup_exists_for_date` |
| Cancel only while `requested` / `assigned` | 409 `not_cancellable` |
| Only the owner can see or cancel a pickup | 404 `pickup_not_found` |
| One household per resident | 409 `household_exists` |

**Consistency (demo scope, no transactions):** the API validates first and then writes the pickup **and** all affected bags in **one atomic batch write**, so a pickup and its bags never disagree. Cancelling sets the pickup to `cancelled` and, in the same batch, returns its bags (only those still pointing at it) to `issued`.
Known trade-off: two schedule requests from the *same* resident at the same instant could both pass validation. The UI disables the button while a request is in flight; Firestore transactions can be added later if needed.

## Security rules

`firestore.rules` — clients **read only their own** data; **no client writes** anywhere.

| Path | Read | Write |
|---|---|---|
| `users/{uid}` | `request.auth.uid == uid` | ✗ |
| `households/{id}` | `resource.data.ownerUid == request.auth.uid` | ✗ |
| `bags/{code}` | `resource.data.ownerUid == request.auth.uid` | ✗ |
| `pickups/{id}` | `resource.data.residentUid == request.auth.uid` | ✗ |
| everything else | ✗ | ✗ |

Client queries must filter on `ownerUid` / `residentUid == <own uid>`. Verified on the live project with real ID tokens: the owner can read their docs and run their queries; another resident gets 403 on direct reads and filtered queries; writes and unauthenticated reads get 403.

## Indexes (`firestore.indexes.json`)

| Collection | Fields | Used by |
|---|---|---|
| `pickups` | `residentUid` ↑, `date` ↓ | live "My pickups" listener |
| `bags` | `ownerUid` ↑, `issuedAt` ↑ | live "My bags" listener |

Backend queries are equality-only and sort in Python, so they need no composite indexes.

## Realtime

The resident dashboard and bags page use Firestore **`onSnapshot`** listeners on the two queries above. When the API changes a pickup or bag (schedule, cancel, and later collection by a collector), the change shows up in the browser within a second or so, with no polling.
