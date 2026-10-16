"use client";

import { useCallback, useEffect, useState } from "react";

import CollectorPage, { type CollectorContext } from "@/components/collector/CollectorPage";
import styles from "@/components/collector/collector.module.css";
import ScanPanel, { type ScanOutcome } from "@/components/collector/ScanPanel";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import Notice from "@/components/ui/Notice";
import { collectorApi, collectorErrorMessage, type HandoverPickup } from "@/lib/collector";
import { formatDay } from "@/lib/dates";

const ARRIVED = new Set(["at_warehouse", "processed"]);

function Handover({ user, profile }: CollectorContext) {
  const [van, setVan] = useState<HandoverPickup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [delivered, setDelivered] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  // Bags handed over this session, so progress doesn't reset as pickups complete.
  const [handedOver, setHandedOver] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      setVan(await collectorApi.handover(user));
      setError(null);
    } catch (err) {
      setError(collectorErrorMessage(err));
    }
  }, [user]);

  useEffect(() => {
    let active = true;
    collectorApi
      .handover(user)
      .then((groups) => active && setVan(groups))
      .catch((err: unknown) => active && setError(collectorErrorMessage(err)));
    return () => {
      active = false;
    };
  }, [user]);

  const onCode = useCallback(
    async (code: string): Promise<ScanOutcome> => {
      try {
        const result = await collectorApi.handoverScan(user, code);
        const group = van?.find((g) => g.pickupId === result.pickupId);
        setHandedOver((codes) => (codes.includes(result.code) ? codes : [...codes, result.code]));
        if (result.pickupDelivered && group) setDelivered((d) => [...d, group.householdName]);
        await load();
        if (result.alreadyScanned) return { ok: true, message: `${result.code} is already at the warehouse` };
        return {
          ok: true,
          message: result.pickupDelivered
            ? `✓ ${result.code} — ${group?.householdName ?? "pickup"} delivered`
            : `✓ ${result.code} handed over`,
        };
      } catch (err) {
        return { ok: false, message: collectorErrorMessage(err) };
      }
    },
    [user, van, load],
  );

  async function simulate(code: string) {
    setBusy(code);
    await onCode(code);
    setBusy(null);
  }

  if (error) return <Alert>{error}</Alert>;
  if (!van) return <FullPageSpinner />;

  const remaining = van.flatMap((g) => g.bags).filter((b) => !ARRIVED.has(b.status)).length;
  const done = handedOver.length;
  const total = remaining + done;
  const pct = total ? Math.round((done / total) * 100) : 0;

  return (
    <div className={styles.stack}>
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Warehouse</p>
        <h1 className={styles.title} data-testid="dashboard-title">Hand over bags</h1>
        <p className={styles.lead}>Scan every bag from your van at the warehouse door.</p>
      </div>

      {delivered.length > 0 && (
        <Notice>
          Delivered: {delivered.join(", ")}. Residents can see it on their tracker now.
        </Notice>
      )}

      {total === 0 ? (
        <EmptyState title="Your van is empty">
          <span>Bags you collect will show up here until you hand them over.</span>
        </EmptyState>
      ) : (
        <>
          <Card>
            <div className={styles.progressLabel}>
              <span>Handed over</span>
              <span data-testid="handover-progress">
                {done}/{total} bags
              </span>
            </div>
            <div className={styles.progress} style={{ marginTop: 8 }}>
              <div className={styles.progressBar} style={{ width: `${pct}%` }} />
            </div>
          </Card>

          {remaining > 0 && (
            <Card title="Scan at the warehouse">
              <ScanPanel onCode={onCode} disabled={busy !== null} />
            </Card>
          )}

          {van.map((group) => (
            <Card key={group.pickupId} data-testid="van-group">
              <div className={styles.group}>
                <div className={styles.groupHead}>
                  <span>{group.householdName}</span>
                  <span className={styles.count}>{formatDay(group.date)}</span>
                </div>
                <ul className={styles.checklist}>
                  {group.bags.map((bag) => {
                    const arrived = ARRIVED.has(bag.status);
                    return (
                      <li
                        key={bag.code}
                        className={`${styles.slot} ${arrived ? styles.slotDone : ""}`}
                        data-testid="van-bag"
                        data-code={bag.code}
                        data-done={arrived}
                      >
                        <span className={styles.tick} aria-hidden="true" />
                        <span className={styles.slotLabel}>
                          <span className={styles.slotTitle}>{bag.code}</span>
                          <span className={styles.slotCode}>{arrived ? "At warehouse" : "In van"}</span>
                        </span>
                        {!arrived && profile.isDemo && (
                          <Button
                            variant="secondary"
                            loading={busy === bag.code}
                            disabled={busy !== null}
                            onClick={() => void simulate(bag.code ?? "")}
                            data-testid="simulate-handover"
                          >
                            Simulate scan
                          </Button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            </Card>
          ))}
          {remaining === 0 && (
            <Button variant="secondary" onClick={() => void load()}>
              Refresh
            </Button>
          )}
        </>
      )}
    </div>
  );
}

export default function CollectorHandover() {
  return <CollectorPage>{(ctx) => <Handover {...ctx} />}</CollectorPage>;
}
