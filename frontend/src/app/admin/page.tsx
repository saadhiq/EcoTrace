"use client";

import { useEffect, useState } from "react";

import AdminPage, { Tile, useAdminData } from "@/components/admin/AdminPage";
import styles from "@/components/admin/admin.module.css";
import CategoryBreakdown from "@/components/resident/insights/CategoryBreakdown";
import Alert from "@/components/ui/Alert";
import Card from "@/components/ui/Card";
import Spinner from "@/components/ui/Spinner";
import { adminErrorMessage, fetchOverview, pct, type AdminContext } from "@/lib/admin";
import { formatDateTime } from "@/lib/dates";
import { fetchTaxonomy } from "@/lib/operator";

const ACTIVE = ["requested", "assigned", "collected", "delivered"];
const sum = (counts: Record<string, number>, keys: string[]) => keys.reduce((n, k) => n + (counts[k] ?? 0), 0);

function Overview({ user, zoneName }: AdminContext) {
  const [range, setRange] = useState<"7d" | "30d">("7d");
  const [synthetic, setSynthetic] = useState(true);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const { data, error } = useAdminData(() => fetchOverview(user, range, synthetic), [range, synthetic]);

  useEffect(() => {
    fetchTaxonomy()
      .then((t) => setLabels(Object.fromEntries(t.categories.map((c) => [c.id, c.label]))))
      .catch(() => undefined);
  }, []);
  const label = (id: string) => labels[id] ?? id;

  return (
    <>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>Overview</h1>
          <p className={styles.muted}>
            {data ? `${data.dateFrom} → ${data.dateTo} · updated ${formatDateTime(new Date(data.generatedAt))}` : "Loading…"}
          </p>
        </div>
        <div className={styles.controls}>
          <div className={styles.segmented} role="group" aria-label="Date range">
            {(["7d", "30d"] as const).map((r) => (
              <button
                key={r}
                type="button"
                className={`${styles.segment} ${range === r ? styles.segmentOn : ""}`}
                aria-pressed={range === r}
                onClick={() => setRange(r)}
              >
                {r === "7d" ? "7 days" : "30 days"}
              </button>
            ))}
          </div>
          <label className={styles.toggle}>
            <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} data-testid="synthetic-toggle" />
            Include synthetic data
          </label>
        </div>
      </div>

      {error ? <Alert>{adminErrorMessage(error)}</Alert> : null}
      {!data && !error && <Spinner />}
      {data && (
        <>
          <div className={`${styles.tiles} ${styles.tiles3}`} data-testid="kpis">
            <Tile label="Pickups today" value={sum(data.pickupsToday, ACTIVE) + (data.pickupsToday.processed ?? 0)}
                  note={`${data.pickupsToday.requested ?? 0} waiting for a collector`} />
            <Tile label="Upcoming (14 days)" value={sum(data.pickupsUpcoming, ["requested", "assigned"])}
                  note={`${data.pickupsUpcoming.requested ?? 0} unassigned`} />
            <Tile label={`Processed (${data.range})`} value={data.pickupsInRange.processed ?? 0}
                  note={`${data.pickupsInRange.missed ?? 0} missed · ${data.pickupsInRange.cancelled ?? 0} cancelled`} />
            <Tile label="Bags classified" value={data.bagsProcessed} note="All time" />
            <Tile label="Active households" value={data.activeHouseholds}
                  note={data.includeSynthetic ? `${data.syntheticHouseholds} synthetic included` : "Real households only"} />
            <Tile label="Recyclable share" value={pct(data.recyclableShare)} note={`${data.collectors} collectors`} />
          </div>

          <Card title="Waste by category" subtitle={`${data.totalQuantity} items, all time`}>
            <CategoryBreakdown
              categories={Object.fromEntries(Object.entries(data.categories).map(([k, q]) => [k, { items: 0, quantity: q }]))}
              total={data.totalQuantity}
              label={label}
              scope="all waste"
            />
          </Card>
          <Card title="Zones" subtitle="Households with processed bags">
            <div className={styles.tableWrap}>
              <table className={styles.table} data-testid="zones">
                <thead>
                  <tr>
                    <th>Zone</th>
                    <th className={styles.num}>Homes</th>
                    <th className={styles.num}>Bags</th>
                    <th className={styles.num}>Recyclable</th>
                    <th className={styles.num}>Eco score</th>
                    <th>Top category</th>
                  </tr>
                </thead>
                <tbody>
                  {data.zones.length === 0 && (
                    <tr>
                      <td colSpan={6} className={styles.muted}>No processed bags yet.</td>
                    </tr>
                  )}
                  {data.zones.map((z) => (
                    <tr key={z.zone}>
                      <td>{zoneName(z.zone)}</td>
                      <td className={styles.num}>{z.households}</td>
                      <td className={styles.num}>{z.bags}</td>
                      <td className={styles.num}>{pct(z.recyclableShare)}</td>
                      <td className={styles.num}>{z.avgEcoScore ?? "—"}</td>
                      <td>{z.topCategory ? label(z.topCategory) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </>
  );
}

export default function AdminOverviewPage() {
  return <AdminPage>{(ctx) => <Overview {...ctx} />}</AdminPage>;
}
