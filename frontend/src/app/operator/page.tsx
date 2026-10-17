"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import ScanPanel, { type ScanOutcome } from "@/components/collector/ScanPanel";
import OperatorPage, { type OperatorContext } from "@/components/operator/OperatorPage";
import styles from "@/components/operator/operator.module.css";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import { formatDateTime, formatDay } from "@/lib/dates";
import { operatorApi, operatorErrorMessage, type QueueItem } from "@/lib/operator";

const bagHref = (code: string) => `/operator/bag?code=${encodeURIComponent(code)}`;

function Queue({ user, zoneName }: OperatorContext) {
  const router = useRouter();
  const [queue, setQueue] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    operatorApi
      .queue(user)
      .then((items) => active && setQueue(items))
      .catch((err: unknown) => active && setError(operatorErrorMessage(err)));
    return () => {
      active = false;
    };
  }, [user]);

  const refresh = useCallback(async () => {
    try {
      setQueue(await operatorApi.queue(user));
      setError(null);
    } catch (err) {
      setError(operatorErrorMessage(err));
    }
  }, [user]);

  // Scanning/typing a bag code opens it (validated by the bag page).
  const onCode = useCallback(
    async (code: string): Promise<ScanOutcome> => {
      try {
        const bag = await operatorApi.bag(user, code);
        if (bag.status !== "at_warehouse" && bag.status !== "processed") {
          return { ok: false, message: "This bag hasn't reached the warehouse yet." };
        }
        router.push(bagHref(bag.code));
        return { ok: true, message: `Opening ${bag.code}…` };
      } catch (err) {
        return { ok: false, message: operatorErrorMessage(err) };
      }
    },
    [user, router],
  );

  return (
    <div className={styles.stack}>
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Warehouse</p>
        <h1 className={styles.title} data-testid="dashboard-title">Bags to classify</h1>
        <p className={styles.lead}>Photograph each bag&apos;s contents and let Gemini list the items. You review and confirm.</p>
      </div>

      <div className={styles.layout}>
        <Card title="Open a bag" subtitle="Scan the bag's QR code or type its code.">
          <ScanPanel onCode={onCode} />
        </Card>

        <section>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>
              Queue {queue && <span className={styles.lead}>({queue.length} waiting, oldest first)</span>}
            </h2>
            <Button variant="ghost" onClick={() => void refresh()}>
              Refresh
            </Button>
          </div>
          {error && <Alert>{error}</Alert>}
          {!queue && !error && <FullPageSpinner />}
          {queue && queue.length === 0 && (
            <EmptyState title="Queue is empty">
              <span>Bags appear here when collectors hand them over at the warehouse.</span>
            </EmptyState>
          )}
          {queue && queue.length > 0 && (
            <ul className={styles.queue} data-testid="queue">
              {queue.map((item) => (
                <li key={item.code}>
                  <Link className={styles.queueItem} href={bagHref(item.code)} data-testid="queue-item" data-code={item.code}>
                    <span className={styles.queueCode}>{item.code}</span>
                    <span className={styles.meta}>
                      <span>{zoneName(item.zone)}</span>
                      {item.pickupDate && <span>· Pickup {formatDay(item.pickupDate)}</span>}
                    </span>
                    <span className={styles.meta}>
                      {item.arrivedAt && <span>Arrived {formatDateTime(new Date(item.arrivedAt))}</span>}
                      {item.hasDraft && <span className={`${styles.pill} ${styles.pillDraft}`}>Analyzed</span>}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default function OperatorQueuePage() {
  return <OperatorPage>{(ctx) => <Queue {...ctx} />}</OperatorPage>;
}
