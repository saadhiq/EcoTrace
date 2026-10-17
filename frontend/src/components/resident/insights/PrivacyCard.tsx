"use client";

import type { User } from "firebase/auth";
import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import Card from "@/components/ui/Card";
import { formatDateTime } from "@/lib/dates";
import { insightsApi, type ConsentView } from "@/lib/insights";

import styles from "./insights.module.css";

/** Opt-in data sharing: off by default, explained plainly, every change logged. */
export default function PrivacyCard({ user, onChange }: { user: User; onChange?: (dataSharing: boolean) => void }) {
  const [view, setView] = useState<ConsentView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    insightsApi
      .consent(user)
      .then((v) => active && setView(v))
      .catch(() => active && setError("Couldn't load your privacy settings."));
    return () => {
      active = false;
    };
  }, [user]);

  async function toggle() {
    if (!view) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await insightsApi.setConsent(user, !view.dataSharing);
      setView(updated);
      onChange?.(updated.dataSharing);
    } catch {
      setError("Couldn't save your choice. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const on = view?.dataSharing ?? false;

  return (
    <Card data-testid="privacy" id="privacy">
      <h2 className={styles.sectionTitle}>Privacy &amp; data sharing</h2>
      <div className={styles.switchRow} style={{ marginTop: 12 }}>
        <div>
          <div style={{ fontWeight: 700 }} id="share-label">
            Share my anonymised waste statistics
          </div>
          <div className={styles.muted} data-testid="consent-status">
            {view === null
              ? "Loading…"
              : on
                ? `On${view.updatedAt ? ` since ${formatDateTime(new Date(view.updatedAt))}` : ""}`
                : `Off${view.updatedAt && view.history.length ? ` since ${formatDateTime(new Date(view.updatedAt))}` : " (default)"}`}
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-labelledby="share-label"
          className={styles.switch}
          disabled={view === null || busy}
          onClick={() => void toggle()}
          data-testid="consent-switch"
        />
      </div>
      {error && (
        <div style={{ marginTop: 12 }}>
          <Alert>{error}</Alert>
        </div>
      )}
      <dl className={styles.explainList}>
        <dt>What would be shared</dt>
        <dd>
          Only category totals from your processed bags (for example “12 plastic items this month”), combined with other
          households: partners only see groups of at least 5 households, so no single home can be picked out.
        </dd>
        <dt>Never shared</dt>
        <dd>Photos, your name, address, phone number, bag codes or the brands you buy.</dd>
        <dt>Why</dt>
        <dd>
          To help recyclers and partners plan collection and recycling capacity — and to show you personal
          sustainable-swap suggestions matched to what you throw away.
        </dd>
        <dt>Your control</dt>
        <dd>
          Sharing is off unless you turn it on. You can withdraw at any time: you are removed from partner statistics and
          your personal swap suggestions are deleted straight away.
        </dd>
      </dl>
      {view && view.history.length > 0 && (
        <p className={styles.small} style={{ marginTop: 12 }} data-testid="consent-history">
          History:{" "}
          {view.history
            .slice(0, 3)
            .map((h) => `${h.value ? "turned on" : "turned off"} ${formatDateTime(new Date(h.at))}`)
            .join(" · ")}
        </p>
      )}
    </Card>
  );
}
