"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";

import ItemEditor, { emptyRow, newRowKey, type Row } from "@/components/operator/ItemEditor";
import OperatorPage, { type OperatorContext } from "@/components/operator/OperatorPage";
import styles from "@/components/operator/operator.module.css";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import CategoryChip from "@/components/ui/CategoryChip";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import Notice from "@/components/ui/Notice";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatDay } from "@/lib/dates";
import { resizeImage } from "@/lib/images";
import {
  isAiFailure,
  operatorApi,
  operatorErrorMessage,
  SAMPLE_PHOTOS,
  type AiResult,
  type BagView,
  type ConfirmResult,
  type Segregation,
  type TokenUsage,
} from "@/lib/operator";
import type { BagStatus } from "@/lib/types";

const MAX_PHOTOS = 3;
const QUALITIES: { id: Segregation; label: string }[] = [
  { id: "good", label: "Good" },
  { id: "mixed", label: "Mixed" },
  { id: "poor", label: "Poor" },
];

type Photo = { id: string; blob: Blob; url: string };
type Meta = { model: string; latencyMs: number | null; tokenUsage: TokenUsage | null };
type Phase = "photos" | "analyzing" | "review" | "done";

function rowsFrom(result: AiResult): Row[] {
  return result.items.map((item, i) => ({ ...item, key: newRowKey(), aiIndex: i, confidence: item.confidence }));
}

function BagScreen({ user, profile, taxonomy, zoneName, code }: OperatorContext & { code: string }) {
  const [bag, setBag] = useState<BagView | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [phase, setPhase] = useState<Phase>("photos");
  const [rows, setRows] = useState<Row[]>([]);
  const [quality, setQuality] = useState<Segregation>("mixed");
  const [hazards, setHazards] = useState<string[]>([]);
  const [aiNotes, setAiNotes] = useState("");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [aiFailed, setAiFailed] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [done, setDone] = useState<ConfirmResult | null>(null);
  const photosRef = useRef<Photo[]>([]);
  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);

  useEffect(() => {
    let active = true;
    operatorApi
      .bag(user, code)
      .then((view) => {
        if (!active) return;
        setBag(view);
        const record = view.record;
        // Reload-safe: reopen a previous analysis (draft) for review.
        if (record?.status === "draft" && record.aiResult) {
          setRows(rowsFrom(record.aiResult));
          setQuality(record.aiResult.segregationQuality);
          setHazards(record.aiResult.hazardFlags);
          setAiNotes(record.aiResult.notes);
          setMeta({ model: record.model ?? "", latencyMs: record.latencyMs, tokenUsage: record.tokenUsage });
          setPhase("review");
        }
      })
      .catch((err: unknown) => active && setLoadError(operatorErrorMessage(err)));
    return () => {
      active = false;
    };
  }, [user, code]);

  // Free preview object URLs on unmount.
  useEffect(() => () => photosRef.current.forEach((p) => URL.revokeObjectURL(p.url)), []);

  // "Analyzing…" stopwatch.
  useEffect(() => {
    if (phase !== "analyzing") return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - started) / 1000), 100);
    return () => clearInterval(timer);
  }, [phase]);

  async function addBlobs(blobs: Blob[]) {
    setError(null);
    const room = MAX_PHOTOS - photos.length;
    const next: Photo[] = [];
    for (const blob of blobs.slice(0, room)) {
      try {
        const resized = await resizeImage(blob);
        next.push({ id: newRowKey(), blob: resized, url: URL.createObjectURL(resized) });
      } catch {
        setError("Couldn't read that image. Try another photo.");
      }
    }
    setPhotos((prev) => [...prev, ...next].slice(0, MAX_PHOTOS));
  }

  async function addSample(file: string) {
    try {
      const res = await fetch(`/samples/${file}`);
      await addBlobs([await res.blob()]);
    } catch {
      setError("Couldn't load the sample photo.");
    }
  }

  function removePhoto(id: string) {
    setPhotos((prev) => {
      const gone = prev.find((p) => p.id === id);
      if (gone) URL.revokeObjectURL(gone.url);
      return prev.filter((p) => p.id !== id);
    });
  }

  async function analyze() {
    setPhase("analyzing");
    setElapsed(0);
    setError(null);
    setAiFailed(null);
    try {
      const out = await operatorApi.analyze(user, code, photos.map((p) => p.blob));
      setRows(rowsFrom(out.result));
      setQuality(out.result.segregationQuality);
      setHazards(out.result.hazardFlags);
      setAiNotes(out.result.notes);
      setMeta({ model: out.model, latencyMs: out.latencyMs, tokenUsage: out.tokenUsage });
      setPhase("review");
    } catch (err) {
      if (isAiFailure(err)) {
        // Manual fallback: the page keeps working without Gemini.
        setAiFailed(operatorErrorMessage(err));
        setRows([emptyRow()]);
        setMeta(null);
        setPhase("review");
      } else {
        setError(operatorErrorMessage(err));
        setPhase("photos");
      }
    }
  }

  function enterManually() {
    setAiFailed(null);
    setRows([emptyRow()]);
    setMeta(null);
    setPhase("review");
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    const finalItems = rows
      .filter((r) => r.name.trim())
      .map((r) => ({
        name: r.name.trim(),
        category: r.category,
        material: r.material.trim(),
        productType: r.productType.trim(),
        brand: r.brand?.trim() || null,
        quantity: r.quantity,
        recyclable: r.recyclable,
        aiIndex: r.aiIndex,
      }));
    if (!finalItems.length) {
      setError("Add at least one item with a name.");
      setBusy(false);
      return;
    }
    try {
      setDone(await operatorApi.confirm(user, code, { finalItems, segregationQuality: quality, hazardFlags: hazards }));
      setPhase("done");
    } catch (err) {
      setError(operatorErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const categories = useMemo(() => taxonomy?.categories ?? [], [taxonomy]);
  const label = (id: string) => categories.find((c) => c.id === id)?.label ?? id;

  if (loadError) {
    return (
      <div className={styles.stack}>
        <Link className={styles.back} href="/operator">← Back to queue</Link>
        <Alert>{loadError}</Alert>
      </div>
    );
  }
  if (!bag || !taxonomy) return <FullPageSpinner />;

  const processed = bag.status === "processed" && phase !== "done";
  const record = bag.record;

  return (
    <div className={styles.stack}>
      <Link className={styles.back} href="/operator">← Back to queue</Link>
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Bag</p>
        <h1 className={`${styles.title} ${styles.mono}`} data-testid="bag-title">{bag.code}</h1>
        <div className={styles.meta} style={{ marginTop: 8 }}>
          <StatusBadge status={(phase === "done" ? "processed" : bag.status) as BagStatus} />
          <span>{zoneName(bag.zone)}</span>
          {bag.pickupDate && <span>· Pickup {formatDay(bag.pickupDate)}</span>}
          <span>· Bag {Math.min(bag.processedInPickup + 1, bag.bagsInPickup)} of {bag.bagsInPickup} in this pickup</span>
        </div>
      </div>

      {processed && record && (
        <Card title="Already processed" data-testid="processed-summary">
          <div className={styles.summary}>
            {record.finalItems.map((item, i) => (
              <span key={i} className={styles.meta}>
                <CategoryChip category={item.category} label={label(item.category)} /> {item.quantity}× {item.name}
              </span>
            ))}
          </div>
        </Card>
      )}

      {!processed && phase !== "done" && (
        <div className={styles.layout}>
          <Card title="Photos" subtitle={`Add 1–${MAX_PHOTOS} photos of the bag's contents.`}>
            <div className={styles.stack}>
              {photos.length > 0 && (
                <div className={styles.photos} data-testid="photos">
                  {photos.map((p) => (
                    <div key={p.id} className={styles.photo}>
                      {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
                      <img src={p.url} alt="Bag contents" />
                      {phase === "photos" && (
                        <button type="button" className={styles.photoRemove} aria-label="Remove photo" onClick={() => removePhoto(p.id)}>
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {phase === "photos" && photos.length < MAX_PHOTOS && (
                <div className={styles.photoActions}>
                  <label className={styles.fileButton}>
                    📷 Take photo
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      onChange={(e) => {
                        void addBlobs(Array.from(e.target.files ?? []));
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <label className={styles.fileButton}>
                    Upload
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      onChange={(e) => {
                        void addBlobs(Array.from(e.target.files ?? []));
                        e.target.value = "";
                      }}
                      data-testid="photo-upload"
                    />
                  </label>
                </div>
              )}
              {phase === "photos" && profile.isDemo && photos.length < MAX_PHOTOS && (
                <div>
                  <p className={styles.fieldLabel}>
                    Use a sample photo <span className={styles.demoTag}>Demo</span>
                  </p>
                  <div className={styles.samples}>
                    {SAMPLE_PHOTOS.map((s) => (
                      <button key={s.file} type="button" className={styles.sample} onClick={() => void addSample(s.file)} data-testid={`sample-${s.file}`}>
                        {/* eslint-disable-next-line @next/next/no-img-element -- static sample thumbnail */}
                        <img src={`/samples/${s.file}`} alt="" loading="lazy" />
                        <span>{s.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {error && phase === "photos" && <Alert>{error}</Alert>}
              {phase === "photos" && (
                <div className={styles.photoActions}>
                  <Button disabled={!photos.length} onClick={() => void analyze()} data-testid="analyze">
                    ✨ Analyze with Gemini
                  </Button>
                  <Button variant="ghost" onClick={enterManually} data-testid="manual">
                    Enter items manually
                  </Button>
                </div>
              )}
            </div>
          </Card>

          <Card>
            {phase === "photos" && (
              <div className={styles.analyzing}>
                <p className={styles.analyzingTitle}>No analysis yet</p>
                <p>Add photos and tap “Analyze with Gemini”. You&apos;ll review the items before anything is saved.</p>
              </div>
            )}
            {phase === "analyzing" && (
              <div className={styles.analyzing} data-testid="analyzing" role="status">
                <span className={styles.sparkle} aria-hidden="true" />
                <p className={styles.analyzingTitle}>Analyzing with Gemini…</p>
                <p className={styles.aiMeta}>{elapsed.toFixed(1)} s</p>
              </div>
            )}
            {phase === "review" && (
              <div className={styles.stack} data-testid="review">
                {aiFailed && <Alert>{aiFailed}</Alert>}
                <div className={styles.sectionHead}>
                  <h2 className={styles.sectionTitle}>{meta ? "Review Gemini's items" : "Enter items"}</h2>
                  {meta && (
                    <span className={styles.aiMeta} data-testid="ai-meta">
                      {meta.model}
                      {meta.latencyMs !== null && ` · ${(meta.latencyMs / 1000).toFixed(1)} s`}
                      {meta.tokenUsage && ` · ${meta.tokenUsage.total.toLocaleString()} tokens`}
                    </span>
                  )}
                </div>
                {aiNotes && meta && <p className={styles.notes}>“{aiNotes}”</p>}
                <ItemEditor rows={rows} categories={categories} onChange={setRows} disabled={busy} />

                <div>
                  <p className={styles.fieldLabel}>Segregation quality</p>
                  <div className={styles.segmented} role="group" aria-label="Segregation quality" data-testid="quality">
                    {QUALITIES.map((q) => (
                      <button key={q.id} type="button" aria-pressed={quality === q.id} onClick={() => setQuality(q.id)}>
                        {q.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className={styles.fieldLabel}>Hazards</p>
                  <div className={styles.flags} data-testid="hazards">
                    {taxonomy.hazardFlags.map((h) => (
                      <button
                        key={h.id}
                        type="button"
                        className={styles.flag}
                        aria-pressed={hazards.includes(h.id)}
                        onClick={() => setHazards((prev) => (prev.includes(h.id) ? prev.filter((x) => x !== h.id) : [...prev, h.id]))}
                      >
                        {h.label}
                      </button>
                    ))}
                  </div>
                </div>
                {error && <Alert>{error}</Alert>}
                <Button block loading={busy} onClick={() => void confirm()} data-testid="confirm">
                  Confirm &amp; mark processed
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {phase === "done" && done && (
        <Card title="Bag processed ✓" data-testid="done">
          <div className={styles.stack}>
            <Notice>
              {done.record.source === "ai" && "Saved exactly as Gemini classified it."}
              {done.record.source === "ai_edited" &&
                `Saved with ${done.record.editCount} correction${done.record.editCount === 1 ? "" : "s"} to Gemini's result.`}
              {done.record.source === "manual" && "Saved from manual entry."}
              {done.pickupProcessed && " This was the last bag of the pickup — the resident's tracker now shows Processed."}
            </Notice>
            <div className={styles.summary}>
              {done.record.finalItems.map((item, i) => (
                <span key={i} className={styles.meta}>
                  <CategoryChip category={item.category} label={label(item.category)} /> {item.quantity}× {item.name}
                </span>
              ))}
            </div>
            <Link href="/operator">
              <Button block>Next bag →</Button>
            </Link>
          </div>
        </Card>
      )}
    </div>
  );
}

function BagPage() {
  const code = (useSearchParams().get("code") ?? "").toUpperCase();
  return <OperatorPage>{(ctx) => <BagScreen key={code} {...ctx} code={code} />}</OperatorPage>;
}

export default function OperatorBag() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <BagPage />
    </Suspense>
  );
}
