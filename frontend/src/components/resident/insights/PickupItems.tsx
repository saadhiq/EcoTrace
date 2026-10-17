"use client";

import type { User } from "firebase/auth";
import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import CategoryChip from "@/components/ui/CategoryChip";
import Spinner from "@/components/ui/Spinner";
import { insightsApi, type PickupDetails } from "@/lib/insights";
import { fetchTaxonomy } from "@/lib/operator";

import styles from "./insights.module.css";

const QUALITY: Record<string, string> = { good: "Well sorted", mixed: "Mixed", poor: "Poorly sorted" };

/** What the warehouse found in each bag of a pickup (final reviewed items; no photos). */
export default function PickupItems({ user, pickupId }: { user: User; pickupId: string }) {
  const [details, setDetails] = useState<PickupDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [hazardLabels, setHazardLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    insightsApi
      .pickupDetails(user, pickupId)
      .then((d) => active && setDetails(d))
      .catch(() => active && setError("Couldn't load the items for this pickup."));
    fetchTaxonomy()
      .then((t) => {
        if (!active) return;
        setLabels(Object.fromEntries(t.categories.map((c) => [c.id, c.label])));
        setHazardLabels(Object.fromEntries(t.hazardFlags.map((h) => [h.id, h.label])));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [user, pickupId]);

  if (error) return <Alert>{error}</Alert>;
  if (!details) return <Spinner />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }} data-testid="pickup-items">
      {details.bags.map((bag) => (
        <div key={bag.code} className={styles.bagDetail}>
          <div className={styles.bagHead}>
            <span>
              Bag {bag.slot} · <span style={{ fontFamily: "var(--font-mono)" }}>{bag.code}</span>
            </span>
            <span>
              {bag.segregationQuality ? QUALITY[bag.segregationQuality] : "Not processed yet"}
              {bag.hazardFlags.length > 0 && ` · ⚠ ${bag.hazardFlags.map((h) => hazardLabels[h] ?? h).join(", ")}`}
            </span>
          </div>
          {bag.items.length > 0 ? (
            <div className={styles.items}>
              {bag.items.map((item, i) => (
                <span key={i} className={styles.itemText} style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                  <CategoryChip category={item.category} label={labels[item.category] ?? item.category} />
                  {item.quantity}× {item.name}
                  {item.brand ? ` (${item.brand})` : ""}
                  {item.recyclable ? " ♻" : ""}
                </span>
              ))}
            </div>
          ) : (
            <span className={styles.small}>Items appear once the warehouse has sorted this bag.</span>
          )}
        </div>
      ))}
    </div>
  );
}
