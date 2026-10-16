"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import CollectorPage, { type CollectorContext } from "@/components/collector/CollectorPage";
import styles from "@/components/collector/collector.module.css";
import ScanPanel, { type ScanOutcome } from "@/components/collector/ScanPanel";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import Notice from "@/components/ui/Notice";
import StatusBadge from "@/components/ui/StatusBadge";
import TextareaField from "@/components/ui/TextareaField";
import {
  collectorApi,
  collectorErrorMessage,
  directionsUrl,
  type CollectorPickupDetail,
  type ScanResult,
} from "@/lib/collector";
import { formatDay } from "@/lib/dates";
import { SLOT_LABELS } from "@/lib/types";

const SCANNED = new Set(["collected", "at_warehouse", "processed"]);

type Mode = null | "missing" | "missed";

function scanMessage(result: ScanResult): string {
  if (result.alreadyScanned) return `Bag ${result.slot} was already scanned`;
  const { scannedCount, bagCount } = result.pickup;
  return scannedCount === bagCount
    ? `✓ Bag ${result.slot} collected — all ${bagCount} bags done`
    : `✓ Bag ${result.slot} collected (${scannedCount}/${bagCount})`;
}

function PickupScreen({ user, profile, zoneName, id }: CollectorContext & { id: string }) {
  const [pickup, setPickup] = useState<CollectorPickupDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(null);
  const [reason, setReason] = useState("");

  useEffect(() => {
    let active = true;
    collectorApi
      .pickup(user, id)
      .then((detail) => active && setPickup(detail))
      .catch((err: unknown) => active && setLoadError(collectorErrorMessage(err)));
    return () => {
      active = false;
    };
  }, [user, id]);

  const onCode = useCallback(
    async (code: string): Promise<ScanOutcome> => {
      try {
        const result = await collectorApi.scan(user, id, code);
        setPickup(result.pickup);
        return { ok: true, message: scanMessage(result) };
      } catch (err) {
        return { ok: false, message: collectorErrorMessage(err) };
      }
    },
    [user, id],
  );

  async function run(label: string, action: () => Promise<CollectorPickupDetail>) {
    setBusy(label);
    setActionError(null);
    try {
      setPickup(await action());
      setMode(null);
      setReason("");
    } catch (err) {
      setActionError(collectorErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function simulate(slot: number) {
    setBusy(`sim-${slot}`);
    setActionError(null);
    try {
      const result = await collectorApi.simulateScan(user, id, slot);
      setPickup(result.pickup);
    } catch (err) {
      setActionError(collectorErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  if (loadError) {
    return (
      <div className={styles.stack}>
        <Link className={styles.back} href="/collector">← Back to today</Link>
        <Alert>{loadError}</Alert>
      </div>
    );
  }
  if (!pickup) return <FullPageSpinner />;

  const active = pickup.mine && pickup.status === "assigned";
  const scanned = pickup.slots.filter((s) => SCANNED.has(s.status)).length;
  const expected = pickup.slots.filter((s) => s.status !== "released").length;
  const allDone = expected > 0 && scanned === expected;
  const pct = expected ? Math.round((scanned / expected) * 100) : 0;

  return (
    <div className={styles.stack}>
      <Link className={styles.back} href={`/collector?date=${pickup.date}`}>
        ← Back to {formatDay(pickup.date)}
      </Link>

      <Card>
        <div className={styles.cardHead}>
          <div>
            <h1 className={styles.title} data-testid="pickup-title">{pickup.householdName}</h1>
            <p className={styles.address}>
              {pickup.addressLine} · {zoneName(pickup.zone)}
            </p>
          </div>
          <StatusBadge status={pickup.status} />
        </div>
        <div className={styles.meta} style={{ marginTop: 12 }}>
          <span className={styles.pill}>{formatDay(pickup.date)}</span>
          <span className={styles.pill}>{SLOT_LABELS[pickup.timeSlot]}</span>
          {pickup.phone && (
            <a className={styles.pill} href={`tel:${pickup.phone.replace(/\s+/g, "")}`}>
              {pickup.phone}
            </a>
          )}
        </div>
        {pickup.notes && <p className={styles.note} style={{ marginTop: 12 }}>“{pickup.notes}”</p>}
        <div className={styles.cardActions} style={{ marginTop: 12 }}>
          <a
            className={styles.linkButton}
            href={directionsUrl(pickup.addressLine, zoneName(pickup.zone))}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open in Google Maps
          </a>
          {pickup.status === "requested" && !pickup.mine && (
            <Button loading={busy === "accept"} onClick={() => void run("accept", () => collectorApi.accept(user, id))}>
              Accept pickup
            </Button>
          )}
        </div>
      </Card>

      {actionError && <Alert>{actionError}</Alert>}

      {active && (
        <Card title="Scan bags" subtitle="Scan each bag's QR code, or type the code printed under it.">
          <ScanPanel onCode={onCode} disabled={busy !== null} />
        </Card>
      )}

      <Card>
        <div className={styles.progressLabel}>
          <span>Bags</span>
          <span data-testid="scan-progress">
            {scanned}/{expected} scanned
          </span>
        </div>
        <div className={styles.progress} style={{ margin: "8px 0 16px" }}>
          <div className={styles.progressBar} style={{ width: `${pct}%` }} />
        </div>
        <ul className={styles.checklist} data-testid="bag-checklist">
          {pickup.slots.map((slot) => {
            const done = SCANNED.has(slot.status);
            const released = slot.status === "released";
            return (
              <li
                key={slot.slot}
                className={`${styles.slot} ${done ? styles.slotDone : ""} ${released ? styles.slotReleased : ""}`}
                data-testid="bag-slot"
                data-done={done}
              >
                <span className={styles.tick} aria-hidden="true" />
                <span className={styles.slotLabel}>
                  <span className={styles.slotTitle}>Bag {slot.slot}</span>
                  <span className={styles.slotCode}>
                    {done ? slot.code : released ? "Not collected" : "Waiting for scan"}
                  </span>
                </span>
                {active && !done && !released && profile.isDemo && (
                  <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                    <span className={styles.demoTag}>Demo</span>
                    <Button
                      variant="secondary"
                      loading={busy === `sim-${slot.slot}`}
                      disabled={busy !== null}
                      onClick={() => void simulate(slot.slot)}
                      data-testid={`simulate-${slot.slot}`}
                    >
                      Simulate scan
                    </Button>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      {active && mode === null && (
        <div className={styles.actions}>
          <Button
            block
            disabled={!allDone || busy !== null}
            loading={busy === "complete"}
            onClick={() => void run("complete", () => collectorApi.complete(user, id))}
            data-testid="complete"
          >
            Complete pickup
          </Button>
          {scanned > 0 && !allDone && (
            <Button variant="secondary" block onClick={() => setMode("missing")} data-testid="complete-missing">
              Complete with missing bags
            </Button>
          )}
          {scanned === 0 && (
            <Button variant="secondary" block onClick={() => setMode("missed")} data-testid="mark-missed">
              Mark missed
            </Button>
          )}
        </div>
      )}

      {active && mode !== null && (
        <div className={styles.reasonPanel} data-testid="reason-panel">
          <TextareaField
            label={mode === "missed" ? "Why was the pickup missed?" : "Why are some bags missing?"}
            placeholder={mode === "missed" ? "e.g. No one answered, gate locked." : "e.g. Resident only had 1 bag ready."}
            maxLength={280}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className={styles.row}>
            <Button variant="secondary" onClick={() => setMode(null)} disabled={busy !== null}>
              Back
            </Button>
            <Button
              disabled={!reason.trim()}
              loading={busy === mode}
              onClick={() =>
                void run(mode, () =>
                  mode === "missed"
                    ? collectorApi.missed(user, id, reason.trim())
                    : collectorApi.complete(user, id, reason.trim()),
                )
              }
              data-testid="confirm-reason"
            >
              {mode === "missed" ? "Mark missed" : "Complete pickup"}
            </Button>
          </div>
        </div>
      )}

      {pickup.status === "collected" && (
        <Notice>
          Collected {scanned} bag{scanned === 1 ? "" : "s"}.{" "}
          <Link href="/collector/handover">Hand them over at the warehouse →</Link>
        </Notice>
      )}
      {pickup.status === "delivered" && <Notice>Delivered to the warehouse. Thank you!</Notice>}
      {pickup.status === "missed" && <Alert>Marked as missed: {pickup.missedReason}</Alert>}
      {pickup.status === "cancelled" && <Alert>The resident cancelled this pickup.</Alert>}
    </div>
  );
}

function PickupPage() {
  const id = useSearchParams().get("id") ?? "";
  return <CollectorPage>{(ctx) => <PickupScreen key={id} {...ctx} id={id} />}</CollectorPage>;
}

export default function CollectorPickup() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <PickupPage />
    </Suspense>
  );
}
