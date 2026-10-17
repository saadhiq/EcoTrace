"use client";

import { useState, type FormEvent } from "react";

import AdminPage, { useAdminData } from "@/components/admin/AdminPage";
import styles from "@/components/admin/admin.module.css";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Notice from "@/components/ui/Notice";
import SelectField from "@/components/ui/SelectField";
import Spinner from "@/components/ui/Spinner";
import {
  adminErrorMessage,
  createPartner,
  fetchDemoKey,
  fetchPartners,
  maskKey,
  pct,
  rotateKey,
  tryPartnerApi,
  type AdminContext,
  type PartnerRow,
} from "@/lib/admin";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

const ENDPOINTS = [
  { value: "/partner/v1/segments", label: "GET /partner/v1/segments" },
  { value: "/partner/v1/segments/beverage-plastic-heavy/recommendations", label: "GET …/segments/beverage-plastic-heavy/recommendations" },
  { value: "/partner/v1/insights", label: "GET /partner/v1/insights" },
];

/** Demo partner key from Secret Manager: masked until revealed; copy without revealing. */
function DemoKey({ ctx, partnerId, onKey }: { ctx: AdminContext; partnerId: string; onKey: (key: string) => void }) {
  const [key, setKey] = useState<string | null>(null);
  const [shown, setShown] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function load(): Promise<string | null> {
    if (key) return key;
    try {
      const k = (await fetchDemoKey(ctx.user, partnerId)).apiKey;
      setKey(k);
      onKey(k);
      return k;
    } catch (err) {
      setNote(adminErrorMessage(err));
      return null;
    }
  }

  return (
    <div className={styles.keyRow}>
      <span className={styles.key} data-testid={`key-${partnerId}`}>
        {key && shown ? key : key ? maskKey(key) : `etp.${partnerId}.${"•".repeat(12)}`}
      </span>
      <Button variant="secondary" onClick={() => void load().then((k) => k && setShown((s) => !s))}>
        {shown ? "Hide" : "Reveal"}
      </Button>
      <Button
        variant="secondary"
        onClick={() =>
          void load().then(async (k) => {
            if (!k) return;
            try {
              await navigator.clipboard.writeText(k);
              setNote("Copied.");
            } catch {
              setNote("Copy failed; reveal and copy manually.");
            }
          })
        }
      >
        Copy
      </Button>
      {note && <span className={styles.muted}>{note}</span>}
    </div>
  );
}

function PartnerCard({ ctx, p, onKey }: { ctx: AdminContext; p: PartnerRow; onKey: (id: string, key: string) => void }) {
  const [rotated, setRotated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <Card title={p.name} subtitle={`${p.catalogSize} products · ${p.active ? "active" : "inactive"}${p.isDemo ? " · demo partner" : ""}`}>
      <div className={styles.partner}>
        <div className={styles.tiles}>
          <div>
            <div className={styles.tileLabel}>Impressions (30 d)</div>
            <div className={styles.tileValue}>{p.impressions}</div>
          </div>
          <div>
            <div className={styles.tileLabel}>Clicks</div>
            <div className={styles.tileValue}>{p.clicks}</div>
          </div>
          <div>
            <div className={styles.tileLabel}>Click-through</div>
            <div className={styles.tileValue}>{pct(p.ctr)}</div>
          </div>
        </div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Top products</th>
                <th className={styles.num}>Shown</th>
                <th className={styles.num}>Clicks</th>
              </tr>
            </thead>
            <tbody>
              {p.topProducts.length === 0 && (
                <tr>
                  <td colSpan={3} className={styles.muted}>No swap impressions yet.</td>
                </tr>
              )}
              {p.topProducts.map((t) => (
                <tr key={t.sku}>
                  <td>{t.name}</td>
                  <td className={styles.num}>{t.impressions}</td>
                  <td className={styles.num}>{t.clicks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {p.isDemo ? (
          <>
            <div className={styles.tileLabel}>Demo API key (from Secret Manager)</div>
            <DemoKey ctx={ctx} partnerId={p.id} onKey={(k) => onKey(p.id, k)} />
          </>
        ) : (
          <div className={styles.keyRow}>
            <span className={styles.key}>{p.keyPrefix}…</span>
            <Button
              variant="secondary"
              onClick={() =>
                rotateKey(ctx.user, p.id)
                  .then((r) => setRotated(r.apiKey))
                  .catch((e: unknown) => setError(adminErrorMessage(e)))
              }
            >
              Rotate key
            </Button>
          </div>
        )}
        {rotated && <Notice>New key (shown once, only its hash is stored): <span className={styles.key}>{rotated}</span></Notice>}
        {error && <Alert>{error}</Alert>}
      </div>
    </Card>
  );
}

function TryApi({ keys }: { keys: Record<string, string> }) {
  const partnerIds = Object.keys(keys);
  const [partner, setPartner] = useState("");
  const [endpoint, setEndpoint] = useState(ENDPOINTS[0].value);
  const [result, setResult] = useState<{ status: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const chosen = partner || partnerIds[0] || "";

  async function run() {
    setBusy(true);
    try {
      const body = await tryPartnerApi(endpoint, keys[chosen]);
      setResult({ status: "200 OK", body: JSON.stringify(body, null, 2) });
    } catch (err) {
      setResult({ status: "Error", body: adminErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Try the partner API" subtitle="Server-to-server API with an X-API-Key header. Anonymized: segments with fewer than 5 consenting households are never returned.">
      <div className={styles.form} data-testid="try-api">
        {partnerIds.length === 0 ? (
          <p className={styles.muted}>Reveal or copy a demo partner key above to try the API.</p>
        ) : (
          <>
            <div className={styles.filters}>
              <SelectField label="Partner key" value={chosen} onChange={(e) => setPartner(e.target.value)}
                           options={partnerIds.map((id) => ({ value: id, label: id }))} />
              <SelectField label="Endpoint" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} options={ENDPOINTS} />
            </div>
            <pre className={styles.code}>
              {`curl ${API_URL}${endpoint} \\\n  -H "X-API-Key: ${maskKey(keys[chosen] ?? "")}"`}
            </pre>
            <Button onClick={() => void run()} loading={busy}>
              Send request
            </Button>
          </>
        )}
        {result && (
          <>
            <div className={styles.tileLabel}>{result.status}</div>
            <pre className={styles.code} data-testid="try-api-result">{result.body}</pre>
          </>
        )}
      </div>
    </Card>
  );
}

function NewPartner({ ctx, onCreated }: { ctx: AdminContext; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const created = await createPartner(ctx.user, name);
      setResult({ ok: true, text: `Created. API key (shown once): ${created.apiKey}` });
      setName("");
      onCreated();
    } catch (err) {
      setResult({ ok: false, text: adminErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Add partner" subtitle="Creates a partner and issues an API key. Only its hash is stored.">
      <form className={styles.form} onSubmit={(e) => void submit(e)}>
        <Field label="Partner name" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" loading={busy}>
          Create partner
        </Button>
        {result && (result.ok ? <Notice>{result.text}</Notice> : <Alert>{result.text}</Alert>)}
      </form>
    </Card>
  );
}

function Partners(ctx: AdminContext) {
  const { data, error, reload } = useAdminData(() => fetchPartners(ctx.user), []);
  const [keys, setKeys] = useState<Record<string, string>>({});
  return (
    <>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>Partners</h1>
          <p className={styles.muted}>Eco-product partners whose catalog powers resident swaps, with engagement over the last 30 days.</p>
        </div>
      </div>
      {error ? <Alert>{adminErrorMessage(error)}</Alert> : null}
      {!data && !error && <Spinner />}
      {data && (
        <div className={styles.grid2}>
          {data.map((p) => (
            <PartnerCard key={p.id} ctx={ctx} p={p} onKey={(id, k) => setKeys((all) => ({ ...all, [id]: k }))} />
          ))}
        </div>
      )}
      <TryApi keys={keys} />
      <NewPartner ctx={ctx} onCreated={reload} />
    </>
  );
}

export default function AdminPartnersPage() {
  return <AdminPage>{(ctx) => <Partners {...ctx} />}</AdminPage>;
}
