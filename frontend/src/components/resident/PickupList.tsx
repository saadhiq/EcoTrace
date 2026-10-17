"use client";

import type { User } from "firebase/auth";
import { useState } from "react";

import PickupItems from "@/components/resident/insights/PickupItems";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import ProgressTracker from "@/components/ui/ProgressTracker";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatDay } from "@/lib/dates";
import type { LiveState } from "@/lib/liveData";
import { cancelPickup, residentErrorMessage } from "@/lib/resident";
import { CANCELLABLE, SLOT_LABELS, type Pickup } from "@/lib/types";

import styles from "./resident.module.css";

function PickupItem({ pickup, user }: { pickup: Pickup; user: User }) {
  const [busy, setBusy] = useState(false);
  const [showItems, setShowItems] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelled = pickup.status === "cancelled";
  const ended = cancelled || pickup.status === "missed";

  async function onCancel() {
    if (!window.confirm(`Cancel the pickup on ${formatDay(pickup.date)}? Its bags will be freed up.`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await cancelPickup(user, pickup.id);
      // The live listener updates this card; nothing else to do.
    } catch (err) {
      setError(residentErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <li
      className={`${styles.pickup} ${ended ? styles.pickupCancelled : ""}`}
      data-testid="pickup"
      data-pickup-id={pickup.id}
      data-status={pickup.status}
    >
      <div className={styles.pickupHead}>
        <div>
          <div className={styles.pickupDate}>{formatDay(pickup.date)}</div>
          <div className={styles.pickupMeta}>{SLOT_LABELS[pickup.timeSlot]}</div>
        </div>
        <StatusBadge status={pickup.status} />
      </div>
      {!ended && <ProgressTracker status={pickup.status} />}
      {pickup.status === "missed" && (
        <p className={styles.notes}>
          The collector couldn&apos;t reach you
          {pickup.missedReason ? `: ${pickup.missedReason.replace(/[.!\s]+$/, "")}` : ""}. Your bags are ready
          to schedule again.
        </p>
      )}
      {pickup.missingBagsReason && (
        <p className={styles.notes}>Some bags weren&apos;t collected: {pickup.missingBagsReason}</p>
      )}
      <div className={styles.chips}>
        {pickup.bagCodes.map((code) => (
          <span key={code} className={styles.chip}>
            {code}
          </span>
        ))}
      </div>
      {pickup.notes && <p className={styles.notes}>“{pickup.notes}”</p>}
      {error && <Alert>{error}</Alert>}
      {pickup.status === "processed" && (
        <div>
          <Button
            variant="secondary"
            onClick={() => setShowItems((v) => !v)}
            aria-expanded={showItems}
            data-testid="show-items"
          >
            {showItems ? "Hide items" : "What was in my bags"}
          </Button>
          {showItems && (
            <div style={{ marginTop: 12 }}>
              <PickupItems user={user} pickupId={pickup.id} />
            </div>
          )}
        </div>
      )}
      {CANCELLABLE.includes(pickup.status) && (
        <div className={styles.pickupFoot}>
          <span className={styles.pickupMeta}>You can cancel until it&apos;s collected.</span>
          <Button variant="secondary" loading={busy} onClick={() => void onCancel()}>
            Cancel pickup
          </Button>
        </div>
      )}
    </li>
  );
}

/** Upcoming (cancellable) pickups first, soonest first; then the rest, newest first. */
function ordered(items: Pickup[]): Pickup[] {
  const active = items.filter((p) => CANCELLABLE.includes(p.status));
  const rest = items.filter((p) => !CANCELLABLE.includes(p.status));
  return [
    ...active.sort((a, b) => a.date.localeCompare(b.date)),
    ...rest.sort((a, b) => b.date.localeCompare(a.date)),
  ];
}

export default function PickupList({ user, pickups }: { user: User; pickups: LiveState<Pickup> }) {
  return (
    <Card data-testid="pickups-card">
      <div className={styles.sectionHead}>
        <h2 className={styles.sectionTitle}>My pickups</h2>
        {pickups.status === "ready" && <span className={styles.liveDot}>Live</span>}
      </div>
      {pickups.status === "loading" && <FullPageSpinner />}
      {pickups.status === "error" && <Alert>{pickups.message}</Alert>}
      {pickups.status === "ready" && pickups.items.length === 0 && (
        <EmptyState title="No pickups yet">
          <span>Schedule your first pickup and track it here in real time.</span>
        </EmptyState>
      )}
      {pickups.status === "ready" && pickups.items.length > 0 && (
        <ul className={styles.list}>
          {ordered(pickups.items).map((pickup) => (
            <PickupItem key={pickup.id} pickup={pickup} user={user} />
          ))}
        </ul>
      )}
    </Card>
  );
}
