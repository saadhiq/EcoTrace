"use client";

import Link from "next/link";

import Button from "@/components/ui/Button";
import StatusBadge from "@/components/ui/StatusBadge";
import { directionsUrl, type CollectorPickup } from "@/lib/collector";
import { SLOT_LABELS } from "@/lib/types";

import styles from "./collector.module.css";

type Props = {
  pickup: CollectorPickup;
  zoneName: string;
  onAccept?: () => void;
  accepting?: boolean;
};

export default function PickupCard({ pickup, zoneName, onAccept, accepting }: Props) {
  const href = `/collector/pickup?id=${encodeURIComponent(pickup.id)}`;
  const bagLabel = `${pickup.bagCount} bag${pickup.bagCount === 1 ? "" : "s"}`;
  return (
    <li className={styles.card} data-testid="collector-pickup" data-pickup-id={pickup.id} data-status={pickup.status}>
      <div className={styles.cardHead}>
        <div>
          <div className={styles.household}>{pickup.householdName}</div>
          <div className={styles.address}>
            {pickup.addressLine} · {zoneName}
          </div>
        </div>
        <StatusBadge status={pickup.status} />
      </div>
      <div className={styles.meta}>
        <span className={styles.pill}>{SLOT_LABELS[pickup.timeSlot]}</span>
        <span className={styles.pill}>
          {pickup.status === "assigned" ? `${pickup.scannedCount}/${bagLabel} scanned` : bagLabel}
        </span>
        {pickup.phone && (
          <a className={styles.pill} href={`tel:${pickup.phone.replace(/\s+/g, "")}`}>
            {pickup.phone}
          </a>
        )}
      </div>
      {pickup.notes && <p className={styles.note}>“{pickup.notes}”</p>}
      {pickup.missedReason && <p className={styles.note}>Missed: {pickup.missedReason}</p>}
      {pickup.missingBagsReason && <p className={styles.note}>Partial: {pickup.missingBagsReason}</p>}
      <div className={styles.cardActions}>
        <a
          className={styles.linkButton}
          href={directionsUrl(pickup.addressLine, zoneName)}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="directions"
        >
          Open in Google Maps
        </a>
        {onAccept ? (
          <Button onClick={onAccept} loading={accepting} data-testid="accept">
            Accept
          </Button>
        ) : (
          <Link className={styles.linkButton} href={href} data-testid="open-pickup">
            {pickup.status === "assigned" ? "Start collection" : "View"}
          </Link>
        )}
      </div>
    </li>
  );
}
