"use client";

import { useState } from "react";

import ResidentPage, { type ResidentContext } from "@/components/resident/ResidentPage";
import rstyles from "@/components/resident/resident.module.css";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import Notice from "@/components/ui/Notice";
import QrCode from "@/components/ui/QrCode";
import StatusBadge from "@/components/ui/StatusBadge";
import { useMyBags } from "@/lib/liveData";
import { requestMoreBags, residentErrorMessage } from "@/lib/resident";
import type { Bag } from "@/lib/types";

import styles from "./bags.module.css";

type Filter = "all" | "issued" | "in_use";

const FILTERS: { id: Filter; label: string; keep: (bag: Bag) => boolean }[] = [
  { id: "all", label: "All", keep: () => true },
  { id: "issued", label: "Ready to use", keep: (b) => b.status === "issued" },
  { id: "in_use", label: "In use", keep: (b) => b.status !== "issued" },
];

function Bags({ user, household, zoneName }: ResidentContext) {
  const bags = useMyBags(user.uid);
  const [filter, setFilter] = useState<Filter>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const all = bags.status === "ready" ? bags.items : [];
  const visible = all.filter(FILTERS.find((f) => f.id === filter)!.keep);
  // Labels are for bags that haven't been collected yet.
  const printable = all.filter((b) => b.status === "issued" || b.status === "scheduled");

  async function onRequestMore() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const count = await requestMoreBags(user);
      setNotice(`${count} new bag${count > 1 ? "s" : ""} issued. Print their labels below.`);
    } catch (err) {
      setError(residentErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className={styles.screen}>
        <div className={styles.head}>
          <div>
            <p className={rstyles.eyebrow}>My bags</p>
            <h1 className={rstyles.title}>Bag QR codes</h1>
            <p className={rstyles.lead}>
              Stick a label on each bag. The collector scans it at your door.
            </p>
          </div>
          <div className={styles.actions}>
            <Button variant="secondary" onClick={() => window.print()} disabled={!printable.length}>
              Print labels
            </Button>
            <Button loading={busy} onClick={() => void onRequestMore()}>
              Request 5 more
            </Button>
          </div>
        </div>

        {(error || notice) && (
          <div className={styles.messages}>
            {error && <Alert>{error}</Alert>}
            {notice && <Notice>{notice}</Notice>}
          </div>
        )}

        {bags.status === "loading" && <FullPageSpinner />}
        {bags.status === "error" && <Alert>{bags.message}</Alert>}
        {bags.status === "ready" && (
          <>
            <div className={styles.filters} role="group" aria-label="Filter bags">
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`${styles.filter} ${filter === f.id ? styles.filterActive : ""}`}
                  aria-pressed={filter === f.id}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label} ({all.filter(f.keep).length})
                </button>
              ))}
            </div>
            {visible.length === 0 ? (
              <EmptyState title="No bags here">
                <span>Request more bags to get new QR codes.</span>
              </EmptyState>
            ) : (
              <div className={styles.grid} data-testid="bag-grid">
                {visible.map((bag) => (
                  <Card key={bag.code} className={styles.bag} data-testid="bag" data-status={bag.status}>
                    <div className={styles.qrBox}>
                      <QrCode value={bag.code} size={120} />
                    </div>
                    <span className={styles.code}>{bag.code}</span>
                    <StatusBadge status={bag.status} />
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Print-only label sheet: QR, code and zone. No personal details. */}
      <div className={styles.sheet} aria-hidden="true">
        {printable.map((bag) => (
          <div key={bag.code} className={styles.label} data-testid="print-label">
            <span className={styles.labelBrand}>EcoTrace</span>
            <QrCode value={bag.code} size={150} />
            <span className={styles.labelCode}>{bag.code}</span>
            <span className={styles.labelZone}>{zoneName(household.zone)}</span>
          </div>
        ))}
      </div>
    </>
  );
}

export default function ResidentBagsPage() {
  return <ResidentPage>{(ctx) => <Bags {...ctx} />}</ResidentPage>;
}
