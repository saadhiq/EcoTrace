"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import CollectorPage, { type CollectorContext } from "@/components/collector/CollectorPage";
import styles from "@/components/collector/collector.module.css";
import PickupCard from "@/components/collector/PickupCard";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import { collectorApi, collectorErrorMessage, type DayView } from "@/lib/collector";
import { colomboDate, formatDay } from "@/lib/dates";
import { useMyRoute } from "@/lib/liveData";

type Load = { status: "loading" } | { status: "ready"; view: DayView } | { status: "error"; message: string };

const REFRESH_MS = 30_000;

function Today({ user, zoneName, date }: CollectorContext & { date: string }) {
  const router = useRouter();
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [accepting, setAccepting] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const route = useMyRoute(user.uid, date);

  const refresh = useCallback(async () => {
    try {
      setLoad({ status: "ready", view: await collectorApi.day(user, date) });
    } catch (err) {
      setLoad({ status: "error", message: collectorErrorMessage(err) });
    }
  }, [user, date]);

  // Refetch on date change, whenever my live route changes, and periodically
  // (new requests from residents arrive only through the API).
  const routeKey = route.status === "ready" ? route.items.map((r) => `${r.pickupId}:${r.status}:${r.scannedCount}`).join() : "";
  useEffect(() => {
    let active = true;
    collectorApi
      .day(user, date)
      .then((view) => active && setLoad({ status: "ready", view }))
      .catch((err: unknown) => active && setLoad({ status: "error", message: collectorErrorMessage(err) }));
    return () => {
      active = false;
    };
  }, [user, date, routeKey]);
  useEffect(() => {
    const timer = setInterval(() => void refresh(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  async function accept(id: string) {
    setAccepting(id);
    setActionError(null);
    try {
      await collectorApi.accept(user, id);
      router.push(`/collector/pickup?id=${encodeURIComponent(id)}`);
    } catch (err) {
      setActionError(collectorErrorMessage(err));
      setAccepting(null);
      void refresh();
    }
  }

  const days = useMemo(
    () => [
      { label: "Yesterday", value: colomboDate(-1) },
      { label: "Today", value: colomboDate(0) },
      { label: "Tomorrow", value: colomboDate(1) },
    ],
    [],
  );

  const setDate = (value: string) => router.replace(`/collector?date=${value}`);

  return (
    <>
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Collector</p>
        <h1 className={styles.title} data-testid="dashboard-title">
          {date === colomboDate(0) ? "Today" : formatDay(date)}
        </h1>
        {load.status === "ready" && (
          <p className={styles.lead}>
            Your zones: {load.view.zones.length ? load.view.zones.map(zoneName).join(", ") : "none assigned yet"}
          </p>
        )}
      </div>

      <div className={styles.dates} role="group" aria-label="Choose a date">
        {days.map((d) => (
          <button
            key={d.value}
            type="button"
            className={`${styles.dateChip} ${d.value === date ? styles.dateChipActive : ""}`}
            aria-pressed={d.value === date}
            onClick={() => setDate(d.value)}
          >
            {d.label}
          </button>
        ))}
        <input
          type="date"
          className={styles.datePicker}
          aria-label="Pick a date"
          value={date}
          onChange={(e) => e.target.value && setDate(e.target.value)}
        />
      </div>

      {actionError && (
        <div className={styles.section}>
          <Alert>{actionError}</Alert>
        </div>
      )}
      {load.status === "loading" && <FullPageSpinner />}
      {load.status === "error" && (
        <div className={styles.section}>
          <Alert>{load.message}</Alert>
          <Button variant="secondary" onClick={() => void refresh()}>
            Try again
          </Button>
        </div>
      )}
      {load.status === "ready" && (
        <>
          <section className={styles.section} data-testid="my-route">
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>My route</h2>
              <span className={styles.count}>{load.view.mine.length} stops</span>
            </div>
            {load.view.mine.length === 0 ? (
              <EmptyState title="No stops yet">
                <span>Accept a pickup below to add it to your route.</span>
              </EmptyState>
            ) : (
              <ul className={styles.list}>
                {load.view.mine.map((p) => (
                  <PickupCard key={p.id} pickup={p} zoneName={zoneName(p.zone)} />
                ))}
              </ul>
            )}
          </section>

          <section className={styles.section} data-testid="available">
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>Available in my zones</h2>
              <Button variant="ghost" onClick={() => void refresh()}>
                Refresh
              </Button>
            </div>
            {load.view.available.length === 0 ? (
              <EmptyState title="Nothing waiting">
                <span>New requests in your zones will appear here.</span>
              </EmptyState>
            ) : (
              <ul className={styles.list}>
                {load.view.available.map((p) => (
                  <PickupCard
                    key={p.id}
                    pickup={p}
                    zoneName={zoneName(p.zone)}
                    onAccept={() => void accept(p.id)}
                    accepting={accepting === p.id}
                  />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  );
}

function TodayPage() {
  const params = useSearchParams();
  const raw = params.get("date");
  const date = raw && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : colomboDate(0);
  return <CollectorPage>{(ctx) => <Today key={date} {...ctx} date={date} />}</CollectorPage>;
}

export default function CollectorToday() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <TodayPage />
    </Suspense>
  );
}
