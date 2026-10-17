"use client";

import AdminPage, { Tile, useAdminData } from "@/components/admin/AdminPage";
import styles from "@/components/admin/admin.module.css";
import Alert from "@/components/ui/Alert";
import Card from "@/components/ui/Card";
import Spinner from "@/components/ui/Spinner";
import { adminErrorMessage, fetchAiQuality, pct, type AdminContext } from "@/lib/admin";

const secs = (ms: number | null) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)} s`);

function AiQualityPanel({ user }: AdminContext) {
  const { data: q, error } = useAdminData(() => fetchAiQuality(user), []);
  return (
    <>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>AI quality</h1>
          <p className={styles.muted}>
            How well Gemini classifies bag photos, measured against what warehouse operators confirm. Real bags only.
          </p>
        </div>
      </div>
      {error ? <Alert>{adminErrorMessage(error)}</Alert> : null}
      {!q && !error && <Spinner />}
      {q && (
        <>
          <div className={`${styles.tiles} ${styles.tiles4}`} data-testid="ai-quality">
            <Tile label="Bags analysed" value={q.bagsAnalyzed}
                  note={`Confirmed bags with a Gemini result (of ${q.recordsConsidered} confirmed).`} />
            <Tile label="Corrected by operator" value={pct(q.correctionRate)}
                  note="Share of analysed bags where the operator changed anything before confirming." />
            <Tile label="Corrections per bag" value={q.avgCorrectionsPerBag ?? "—"}
                  note="Average number of item edits per analysed bag." />
            <Tile label="Average latency" value={secs(q.avgLatencyMs)} note="Photo upload to Gemini answer." />
            <Tile label="p95 latency" value={secs(q.p95LatencyMs)} note="95% of classifications finish within this time." />
            <Tile label="Low-confidence items" value={pct(q.lowConfidenceShare)}
                  note="Items Gemini rated below 60% confidence; the UI flags these for review." />
            <Tile label="Failures" value={q.failures} note="Gemini calls that timed out, errored or returned invalid output." />
            <Tile label="Manual fallbacks" value={q.manualFallbacks} note="Bags the operator entered by hand instead." />
          </div>
          <div className={styles.grid2}>
            <Card title="What operators changed" subtitle="Items added, removed or modified across all corrections">
              <table className={styles.table}>
                <tbody>
                  <tr>
                    <td>Added (Gemini missed an item)</td>
                    <td className={styles.num}>{q.itemsAdded}</td>
                  </tr>
                  <tr>
                    <td>Removed (Gemini saw an item that wasn&apos;t there)</td>
                    <td className={styles.num}>{q.itemsRemoved}</td>
                  </tr>
                  <tr>
                    <td>Modified (wrong category, quantity or name)</td>
                    <td className={styles.num}>{q.itemsModified}</td>
                  </tr>
                </tbody>
              </table>
              {q.estimatedEditRecords > 0 && (
                <p className={styles.muted} style={{ marginTop: 8 }}>
                  {q.estimatedEditRecords} older bag{q.estimatedEditRecords === 1 ? "" : "s"} predate the detailed edit log;
                  their split is estimated from item counts.
                </p>
              )}
            </Card>
            <Card title="Models" subtitle="Gemini model that produced each analysed bag">
              <table className={styles.table}>
                <tbody>
                  {Object.entries(q.models).map(([m, n]) => (
                    <tr key={m}>
                      <td>{m}</td>
                      <td className={styles.num}>{n}</td>
                    </tr>
                  ))}
                  {Object.keys(q.models).length === 0 && (
                    <tr>
                      <td className={styles.muted}>No analysed bags yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </Card>
          </div>
        </>
      )}
    </>
  );
}

export default function AdminAiQualityPage() {
  return <AdminPage>{(ctx) => <AiQualityPanel {...ctx} />}</AdminPage>;
}
