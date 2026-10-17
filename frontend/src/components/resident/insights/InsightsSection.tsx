"use client";

import { useEffect, useState } from "react";

import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import { formatDateTime } from "@/lib/dates";
import {
  LEDGER_LABELS,
  SCORE_EXPLANATION,
  useHouseholdStats,
  useRecentPoints,
  type HouseholdStats,
} from "@/lib/insights";
import { fetchTaxonomy } from "@/lib/operator";

import CategoryBreakdown from "./CategoryBreakdown";
import styles from "./insights.module.css";
import TrendChart from "./TrendChart";

const PARTS: { key: keyof NonNullable<HouseholdStats["scoreParts"]>; label: string; max: number }[] = [
  { key: "sorting", label: "Sorting", max: 50 },
  { key: "recycling", label: "Recycling", max: 30 },
  { key: "hazards", label: "Safe hazards", max: 20 },
];

type StatsState = ReturnType<typeof useHouseholdStats>;

/** Eco score, points, recyclable share, category breakdown and trend - all live. */
export default function InsightsSection({ uid, statsState }: { uid: string; statsState: StatsState }) {
  const points = useRecentPoints(uid, 5);
  const [labels, setLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchTaxonomy()
      .then((t) => setLabels(Object.fromEntries(t.categories.map((c) => [c.id, c.label]))))
      .catch(() => undefined);
  }, []);
  const label = (id: string) => labels[id] ?? id;

  if (statsState.status === "loading") return <FullPageSpinner />;
  const stats = statsState.status === "ready" ? statsState.value : null;

  return (
    <section className={styles.section} data-testid="insights" aria-labelledby="insights-title">
      <div className={styles.sectionHead}>
        <h2 id="insights-title" className={styles.sectionTitle}>
          Your insights
        </h2>
        {stats?.lastUpdated && <span className={styles.small}>Updated {formatDateTime(stats.lastUpdated)}</span>}
      </div>

      {!stats || stats.bagsProcessed === 0 ? (
        <EmptyState title="Your insights appear after your first processed pickup">
          <span>Once the warehouse sorts your bags, you&apos;ll see your eco score, points and what you throw away.</span>
        </EmptyState>
      ) : (
        <>
          <div className={styles.tiles}>
            <Card className={styles.tile} data-testid="eco-score">
              <span className={styles.tileLabel}>Eco score</span>
              <span className={styles.hero}>
                <span className={styles.heroNumber}>{stats.ecoScore}</span>
                <span className={styles.heroUnit}>/ 100</span>
              </span>
              {stats.scoreParts && (
                <div className={styles.parts}>
                  {PARTS.map((p) => (
                    <div key={p.key} className={styles.part}>
                      <span>{p.label}</span>
                      <span className={styles.meter} aria-hidden="true">
                        <span className={styles.meterFill} style={{ display: "block", width: `${(stats.scoreParts![p.key] / p.max) * 100}%` }} />
                      </span>
                      <span className={styles.partValue}>
                        {Math.round(stats.scoreParts![p.key])} / {p.max}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className={styles.explain}>
                <strong>How this is calculated:</strong> {SCORE_EXPLANATION}
              </p>
            </Card>

            <Card className={styles.tile} data-testid="points">
              <span className={styles.tileLabel}>Points</span>
              <span className={styles.hero}>
                <span className={styles.heroNumber}>{stats.points}</span>
                <span className={styles.heroUnit}>pts</span>
              </span>
              {points.status === "ready" && points.value.length > 0 && (
                <ul className={styles.ledger}>
                  {points.value.map((e) => (
                    <li key={e.id} className={styles.ledgerRow}>
                      <span>
                        {LEDGER_LABELS[e.reason] ?? e.reason}
                        <span className={styles.small}> · {e.at ? formatDateTime(e.at) : ""}</span>
                      </span>
                      <span className={styles.ledgerPoints}>+{e.points}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className={styles.explain}>+10 per bag · +5 well sorted · +5 hazards packed separately</p>
            </Card>

            <Card className={styles.tile} data-testid="recyclable">
              <span className={styles.tileLabel}>Recyclable share</span>
              <span className={styles.hero}>
                <span className={styles.heroNumber}>
                  {stats.recyclableShare === null ? "–" : Math.round(stats.recyclableShare * 100)}
                </span>
                <span className={styles.heroUnit}>%</span>
              </span>
              <span className={styles.muted}>of your waste (by item count) can be recycled.</span>
              <span className={styles.muted}>
                {stats.bagsProcessed} bags · {stats.pickupsProcessed} pickups processed
              </span>
              <span className={styles.muted}>
                Sorting: {stats.segregation.good ?? 0} good · {stats.segregation.mixed ?? 0} mixed · {stats.segregation.poor ?? 0}{" "}
                poor
              </span>
            </Card>
          </div>

          <div className={styles.charts}>
            <Card title="What you throw away" subtitle={`${stats.totalQuantity} items across ${stats.bagsProcessed} bags`}>
              <CategoryBreakdown categories={stats.categories} total={stats.totalQuantity} label={label} />
            </Card>
            <Card title="Eco score by pickup" subtitle="Each point is one processed pickup.">
              <TrendChart points={stats.byPickup} />
            </Card>
          </div>
        </>
      )}
    </section>
  );
}
