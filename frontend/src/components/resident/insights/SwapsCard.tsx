"use client";

import type { User } from "firebase/auth";
import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import CategoryChip from "@/components/ui/CategoryChip";
import EmptyState from "@/components/ui/EmptyState";
import { ApiError } from "@/lib/api";
import { swapsApi, type SwapPick, type SwapsResponse } from "@/lib/insights";
import { fetchTaxonomy } from "@/lib/operator";

import styles from "./insights.module.css";

type Load = { status: "loading" } | { status: "ready"; data: SwapsResponse } | { status: "consent" } | { status: "error" };

const LKR = new Intl.NumberFormat("en-LK", { style: "currency", currency: "LKR", maximumFractionDigits: 0 });

/** Personal sustainable swaps from partner catalogs (only with data-sharing consent). */
export default function SwapsCard({ user, consentKey, statsHash }: { user: User; consentKey: number; statsHash: string | null }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [opening, setOpening] = useState<string | null>(null);

  useEffect(() => {
    fetchTaxonomy()
      .then((t) => setLabels(Object.fromEntries(t.categories.map((c) => [c.id, c.label]))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let active = true;
    swapsApi
      .list(user)
      .then((data) => active && setLoad({ status: "ready", data }))
      .catch((err: unknown) => {
        if (!active) return;
        setLoad(err instanceof ApiError && err.detail === "consent_required" ? { status: "consent" } : { status: "error" });
      });
    return () => {
      active = false;
    };
  }, [user, consentKey, statsHash]);

  function view(pick: SwapPick) {
    setOpening(pick.sku);
    // Demo partners link to our own fictional store page; pass the product details along.
    const url = pick.url.startsWith("/")
      ? `${pick.url}&${new URLSearchParams({ name: pick.name, partnerName: pick.partnerName, benefit: pick.ecoBenefit, price: String(pick.price), category: pick.category })}`
      : pick.url;
    window.open(url, "_blank", "noopener");
    // Anonymous click count (partner + product + day); never blocks the user.
    swapsApi
      .click(user, pick.sku)
      .catch(() => undefined)
      .finally(() => setOpening(null));
  }

  return (
    <Card data-testid="swaps">
      <div className={styles.sectionHead} style={{ marginBottom: 8 }}>
        <h2 className={styles.sectionTitle}>Sustainable swaps for you</h2>
        {load.status === "ready" && load.data.picks.length > 0 && (
          <span className={styles.small} data-testid="swaps-source">
            {load.data.source === "fallback" ? "Matched from your waste data" : `Ranked by Gemini from your waste data`}
          </span>
        )}
      </div>

      {load.status === "loading" && (
        <div className={styles.tips} aria-busy="true">
          {[0, 1].map((i) => (
            <div key={i} className={styles.skeleton} />
          ))}
        </div>
      )}

      {load.status === "error" && <Alert>Couldn&apos;t load swaps right now.</Alert>}

      {load.status === "consent" && (
        <div data-testid="swaps-consent" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <p className={styles.muted}>
            Get product swaps matched to what you actually throw away — for example a reusable bottle if you dispose of
            lots of plastic bottles. Suggestions come from our recycling partners and use your waste statistics, so they
            need your data-sharing consent. Partners never see your household&apos;s data.
          </p>
          <div>
            <Button
              variant="secondary"
              onClick={() => document.getElementById("privacy")?.scrollIntoView({ behavior: "smooth", block: "center" })}
            >
              Turn on in Privacy &amp; data sharing ↓
            </Button>
          </div>
        </div>
      )}

      {load.status === "ready" && load.data.picks.length === 0 && (
        <EmptyState title="No swaps yet">
          <span>Swaps appear once the warehouse has processed some of your bags.</span>
        </EmptyState>
      )}

      {load.status === "ready" && load.data.picks.length > 0 && (
        <ul className={styles.tips} data-testid="swap-list">
          {load.data.picks.map((pick) => (
            <li key={pick.sku} className={styles.tip} data-sku={pick.sku}>
              <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <CategoryChip category={pick.category} label={labels[pick.category] ?? pick.category} />
                <span className={styles.small}>{pick.partnerName}</span>
              </span>
              <span className={styles.tipTitle}>{pick.name}</span>
              <span className={styles.tipBody}>“{pick.reason}”</span>
              <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span className={styles.small}>
                  ♻ {pick.ecoBenefit} · {LKR.format(pick.price)}
                </span>
                <Button variant="secondary" loading={opening === pick.sku} onClick={() => view(pick)} data-testid="swap-view">
                  View
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
