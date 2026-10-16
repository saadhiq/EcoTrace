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
| `zones` | string[] | **collectors only**: zones they cover (set by the seed script now, by an admin later) |

`GET /me` also returns `isDemo` (true only for the shared `demo-*` accounts), which unlocks demo-only helpers such as "Simulate scan". The server checks the same uid list.

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
| `pickupId` | string \| null | set while attached to a pickup (`scheduled` and after collection) |
| `collectorUid` | string \| null | set when a collector scans the bag (drives the warehouse handover) |
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
| `status` | `requested` → `assigned` → `collected` → `delivered` → `processed`; or `cancelled` / `missed` | see [state machine](#status-state-machine) |
| `collectorUid` | string \| null | set when a collector accepts |
| `statusHistory` | `[{ status, at, by }]` | append-only |
| `createdAt` | timestamp | |
| `assignedAt`, `collectedAt`, `deliveredAt` | timestamp \| null | set on the matching transition |
| `missedReason` | string \| null | why the collector marked it missed (resident not available) |
| `missingBagsReason` | string \| null | partial completion: why some bags weren't collected |

### `routes/{pickupId}`
A **code-free mirror** of each pickup once a collector accepts it, so the collector's browser can listen live to "My route". Firestore rules can't hide individual fields, so letting collectors read `pickups` would expose every bag code before it's scanned. The backend writes this doc in the **same batch** as every collector-side pickup change (accept, scan, complete, missed, handover) and when a resident cancels an assigned pickup.

| Field | Type |
|---|---|
| `collectorUid` | string |
| `date`, `timeSlot`, `status`, `zone` | as on the pickup |
| `householdName`, `addressLine` | from the household |
| `bagCount`, `scannedCount` | int |
| `updatedAt` | timestamp |

## Status state machine

Defined once in `backend/app/transitions.py`; every endpoint changes status through `advance_pickup` / `advance_bag`, which reject anything else with `409 invalid_transition` and append to `statusHistory`.

**Pickup**

| From | To | Who / when |
|---|---|---|
| `requested` | `assigned` | collector accepts (pickup must be in one of their zones) |
| `requested` | `cancelled` | resident |
| `assigned` | `collected` | collector completes (all bags scanned, or some with a reason) |
| `assigned` | `missed` | collector, with a reason, **before any bag is scanned** |
| `assigned` | `cancelled` | resident, **only before any bag is scanned** |
| `collected` | `delivered` | automatically, when every attached bag reaches `at_warehouse` |
| `delivered` | `processed` | warehouse (next step) |
| `cancelled`, `missed`, `processed` | — | final |

**Bag**

| From | To | When |
|---|---|---|
| `issued` | `scheduled` | added to a pickup |
| `scheduled` | `collected` | scanned at the door |
| `scheduled` | `issued` | pickup cancelled or missed, or bag left out of a partial completion (detached: `pickupId = null`) |
| `collected` | `at_warehouse` | scanned at the warehouse handover |
| `at_warehouse` | `processed` | warehouse (next step) |

## Rules enforced by the API

| Rule | Error |
|---|---|
| Date from tomorrow to 14 days ahead (Colombo time) | 422 `date_out_of_range` |
| 1–5 bags, no duplicates | 422 `invalid_bag_count` / `duplicate_bags` |
| Every bag belongs to the household (unknown codes give the same error, so codes can't be probed) | 422 `bag_not_owned` |
| Every bag is `issued` (not already in a pickup) | 409 `bag_not_available` |
| At most one active pickup per household per date (`cancelled` and `missed` free the date) | 409 `pickup_exists_for_date` |
| Cancel only while `requested` / `assigned` and before any bag is scanned | 409 `not_cancellable` |
| Only the owner can see or cancel a pickup | 404 `pickup_not_found` |
| One household per resident | 409 `household_exists` |

### Collector rules

| Rule | Error |
|---|---|
| Lists show **no bag codes**; a pickup's bags are numbered slots whose code appears only once scanned | — |
| Accept only `requested` pickups in my zones (accepting my own again is a no-op) | 409 `pickup_not_available` / 403 `outside_your_zones` |
| Scan / complete / missed only on pickups **assigned to me** and still `assigned` | 404 `pickup_not_found` / 409 `pickup_not_active` |
| Scanned code fails the check character (typo) | 422 `invalid_code` |
| Valid code that doesn't exist | 404 `unknown_code` |
| Bag isn't part of this pickup | 409 `wrong_pickup` ("This bag belongs to another pickup") |
| Same bag scanned again | 200 with `alreadyScanned: true`, nothing written |
| Complete with nothing scanned | 409 `nothing_scanned` (use missed) |
| Complete with unscanned bags needs a reason; those bags return to `issued` | 422 `missing_reason_required` |
| Missed needs a reason and no scanned bags | 422 `reason_required` / 409 `bags_already_scanned` |
| Handover: bag must be `collected` by me on a completed pickup; repeat scans are no-ops | 409 `not_in_your_van` |
| Simulated scans are for demo accounts only | 403 `demo_only` |

**Consistency (demo scope, no transactions):** the API validates first and then writes the pickup **and** all affected bags in **one atomic batch write**, so a pickup and its bags never disagree. Cancelling sets the pickup to `cancelled` and, in the same batch, returns its bags (only those still pointing at it) to `issued`.
Known trade-offs: two schedule requests from the *same* resident at the same instant could both pass validation, and two collectors accepting the same pickup at the same instant means the last write wins. The UI disables the button while a request is in flight; Firestore transactions can be added later if needed.

## Security rules

`firestore.rules` — clients **read only their own** data; **no client writes** anywhere.

| Path | Read | Write |
|---|---|---|
| `users/{uid}` | `request.auth.uid == uid` | ✗ |
| `households/{id}` | `resource.data.ownerUid == request.auth.uid` | ✗ |
| `bags/{code}` | `resource.data.ownerUid == request.auth.uid` | ✗ |
| `pickups/{id}` | `resource.data.residentUid == request.auth.uid` (residents only — collectors never read pickups, so codes can't leak) | ✗ |
| `routes/{pickupId}` | `resource.data.collectorUid == request.auth.uid` | ✗ |
| everything else | ✗ | ✗ |

Client queries must filter on `ownerUid` / `residentUid` / `collectorUid == <own uid>`. Requested pickups available to collectors come **only through the API**. Verified on the live project with real ID tokens: the owner can read their docs and run their queries; another resident gets 403 on direct reads and filtered queries; writes and unauthenticated reads get 403.

## Indexes (`firestore.indexes.json`)

| Collection | Fields | Used by |
|---|---|---|
| `pickups` | `residentUid` ↑, `date` ↓ | live "My pickups" listener |
| `bags` | `ownerUid` ↑, `issuedAt` ↑ | live "My bags" listener |

Backend queries are equality-only (including `zone in [...]`) and sort in Python, so they need no composite indexes. The collector's live query on `routes` (`collectorUid ==` and `date ==`) is equality-only too.

## Realtime

The resident dashboard and bags page use Firestore **`onSnapshot`** listeners on the two queries above; the collector's "My route" listens to `routes`. When the API changes a pickup or bag (schedule, cancel, and later collection by a collector), the change shows up in the browser within a second or so, with no polling.
