"use client";

import type { User } from "firebase/auth";
import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import Card from "@/components/ui/Card";
import CategoryChip from "@/components/ui/CategoryChip";
import { formatDateTime } from "@/lib/dates";
import { insightsApi, LANG_LABELS, type Lang, type TipsResponse } from "@/lib/insights";
import { fetchTaxonomy } from "@/lib/operator";

import styles from "./insights.module.css";

const LANGS: Lang[] = ["en", "si", "ta"];

function caption(res: TipsResponse): string {
  switch (res.source) {
    case "gemini":
      return `Personalised by Gemini from your stats · ${res.model}${res.latencyMs ? ` · ${(res.latencyMs / 1000).toFixed(1)} s` : ""}`;
    case "cache":
      return `Personalised by Gemini from your stats${res.generatedAt ? ` · ${formatDateTime(new Date(res.generatedAt))}` : ""}`;
    case "fallback":
      return "General tips — personalised tips are unavailable right now.";
    default:
      return "General tips — personalised tips appear after your first processed pickup.";
  }
}

/** 3 tips in English / Sinhala / Tamil (Gemini, from aggregated stats only; cached server-side). */
export default function TipsCard({ user, statsHash }: { user: User; statsHash: string | null }) {
  const [lang, setLang] = useState<Lang>("en");
  const [result, setResult] = useState<{ lang: Lang; data: TipsResponse } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchTaxonomy()
      .then((t) => setLabels(Object.fromEntries(t.categories.map((c) => [c.id, c.label]))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let active = true;
    insightsApi
      .tips(user, lang)
      .then((data) => {
        if (!active) return;
        setResult({ lang, data });
        setError(null);
      })
      .catch(() => active && setError("Couldn't load tips. Check your connection."));
    return () => {
      active = false;
    };
    // statsHash: re-ask when the household stats change (server regenerates once, then caches).
  }, [user, lang, statsHash]);

  const loading = !error && result?.lang !== lang;
  const data = result?.lang === lang ? result.data : null;

  return (
    <Card data-testid="tips">
      <div className={styles.sectionHead} style={{ marginBottom: 0 }}>
        <h2 className={styles.sectionTitle}>Tips for your household</h2>
        <div className={styles.langs} role="group" aria-label="Tip language">
          {LANGS.map((l) => (
            <button key={l} type="button" lang={l} aria-pressed={lang === l} onClick={() => setLang(l)} data-testid={`lang-${l}`}>
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div style={{ marginTop: 16 }}>
          <Alert>{error}</Alert>
        </div>
      )}
      {loading && (
        <div className={styles.tips} aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className={styles.skeleton} />
          ))}
        </div>
      )}
      {data && (
        <>
          <ul className={styles.tips} lang={data.lang} data-testid="tip-list" data-source={data.source}>
            {data.tips.map((tip, i) => (
              <li key={i} className={styles.tip}>
                <span lang="en">
                  <CategoryChip category={tip.category} label={labels[tip.category] ?? tip.category} />
                </span>
                <span className={styles.tipTitle}>{tip.title}</span>
                <span className={styles.tipBody}>{tip.body}</span>
              </li>
            ))}
          </ul>
          <p className={styles.small} style={{ marginTop: 12 }} data-testid="tips-caption">
            {caption(data)}
          </p>
        </>
      )}
    </Card>
  );
}
