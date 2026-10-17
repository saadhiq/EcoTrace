"use client";

import { useEffect, useState } from "react";

import AdminPage, { useAdminData } from "@/components/admin/AdminPage";
import styles from "@/components/admin/admin.module.css";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Notice from "@/components/ui/Notice";
import SelectField from "@/components/ui/SelectField";
import Spinner from "@/components/ui/Spinner";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  adminErrorMessage,
  assignPickup,
  fetchPickup,
  fetchPickups,
  fetchUsers,
  type AdminContext,
  type AdminUser,
  type PickupDetail,
} from "@/lib/admin";
import { colomboDate, formatDateTime } from "@/lib/dates";
import { fetchZones } from "@/lib/resident";
import { SLOT_LABELS, STATUS_LABELS, type PickupStatus, type TimeSlot, type Zone } from "@/lib/types";

const STATUSES: PickupStatus[] = ["requested", "assigned", "collected", "delivered", "processed", "missed", "cancelled"];

function Drawer({ ctx, id, collectors, onClose, onChanged }: {
  ctx: AdminContext;
  id: string;
  collectors: AdminUser[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const { data, error, setData } = useAdminData(() => fetchPickup(ctx.user, id), [id]);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const names = Object.fromEntries(collectors.map((c) => [c.uid, c.name]));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function reassign(detail: PickupDetail) {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await assignPickup(ctx.user, detail.pickup.id, choice);
      setData(updated);
      setMessage({ ok: true, text: `Assigned to ${updated.pickup.collectorName ?? choice}.` });
      onChanged();
    } catch (err) {
      setMessage({ ok: false, text: adminErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  const eligible = data ? collectors.filter((c) => c.zones.includes(data.pickup.zone) && c.uid !== data.pickup.collectorUid) : [];
  const demoLocked = ctx.isDemo && data && !data.pickup.isDemo;

  return (
    <>
      <div className={styles.scrim} onClick={onClose} aria-hidden="true" />
      <aside className={styles.drawer} role="dialog" aria-modal="true" aria-label="Pickup detail" data-testid="pickup-drawer">
        <div className={styles.drawerHead}>
          <div>
            <h2 className={styles.title}>{data?.pickup.householdName ?? "Pickup"}</h2>
            {data && (
              <p className={styles.muted}>
                {data.pickup.date} · {SLOT_LABELS[data.pickup.timeSlot as TimeSlot] ?? data.pickup.timeSlot} ·{" "}
                {ctx.zoneName(data.pickup.zone)}
              </p>
            )}
          </div>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>
        {error ? <Alert>{adminErrorMessage(error)}</Alert> : null}
        {!data && !error && <Spinner />}
        {data && (
          <>
            <div className={styles.keyRow}>
              <StatusBadge status={data.pickup.status as PickupStatus} />
              <span className={styles.muted}>
                {data.pickup.bagCount} bag{data.pickup.bagCount === 1 ? "" : "s"} · collector: {data.pickup.collectorName ?? "none"}
              </span>
              {data.pickup.isDemo && <span className={styles.tag}>demo data</span>}
            </div>
            {data.addressLine && <p className={styles.muted}>{data.addressLine}</p>}

            <section>
              <h3 className={styles.tileLabel}>Timeline</h3>
              <ol className={styles.timeline} data-testid="timeline">
                {data.timeline.map((e, i) => (
                  <li key={i} className={`${styles.event} ${e.kind === "bag" ? styles.eventBag : ""}`}>
                    <strong>
                      {e.kind === "bag" ? `Bag ${e.bagCode}: ` : "Pickup: "}
                      {STATUS_LABELS[e.status as PickupStatus] ?? e.status}
                    </strong>
                    <div className={styles.eventMeta}>
                      {formatDateTime(new Date(e.at))} · by {names[e.by] ?? e.by}
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            <section className={styles.form}>
              <h3 className={styles.tileLabel}>{data.pickup.collectorUid ? "Reassign collector" : "Assign collector"}</h3>
              {!data.canReassign ? (
                <p className={styles.muted}>Not reassignable: only pickups that are requested, or assigned with no bag scanned yet.</p>
              ) : demoLocked ? (
                <p className={styles.muted}>Disabled in the public demo. You can reassign demo and synthetic households only.</p>
              ) : (
                <>
                  <SelectField
                    label="Collector"
                    value={choice}
                    onChange={(e) => setChoice(e.target.value)}
                    placeholder={eligible.length ? "Choose a collector" : "No other collector covers this zone"}
                    options={eligible.map((c) => ({ value: c.uid, label: `${c.name}${c.isSynthetic ? " (synthetic)" : ""}` }))}
                    data-testid="collector-select"
                  />
                  <Button onClick={() => void reassign(data)} disabled={!choice} loading={busy}>
                    {data.pickup.collectorUid ? "Reassign" : "Assign"}
                  </Button>
                </>
              )}
              {message && (message.ok ? <Notice>{message.text}</Notice> : <Alert>{message.text}</Alert>)}
            </section>
          </>
        )}
      </aside>
    </>
  );
}

function Pickups(ctx: AdminContext) {
  const [filters, setFilters] = useState({ date: colomboDate(), zone: "", status: "", page: 1 });
  const [zones, setZones] = useState<Zone[]>([]);
  const [collectors, setCollectors] = useState<AdminUser[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const { data, error, reload } = useAdminData(() => fetchPickups(ctx.user, filters), [filters]);

  useEffect(() => {
    fetchZones().then(setZones).catch(() => undefined);
    fetchUsers(ctx.user, "collector").then(setCollectors).catch(() => undefined);
  }, [ctx.user]);

  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;

  return (
    <>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>Pickups</h1>
          <p className={styles.muted}>Open a pickup to see its full timeline and assign or reassign a collector.</p>
        </div>
      </div>
      <Card>
        <div className={styles.filters}>
          <Field label="Date" type="date" value={filters.date} onChange={(e) => e.target.value && set({ date: e.target.value })} />
          <SelectField label="Zone" value={filters.zone} onChange={(e) => set({ zone: e.target.value })}
                       options={[{ value: "", label: "All zones" }, ...zones.map((z) => ({ value: z.id, label: z.name }))]} />
          <SelectField label="Status" value={filters.status} onChange={(e) => set({ status: e.target.value })}
                       options={[{ value: "", label: "All statuses" }, ...STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))]} />
        </div>
      </Card>
      {error ? <Alert>{adminErrorMessage(error)}</Alert> : null}
      <Card>
        {!data && !error && <Spinner />}
        {data && (
          <>
            <div className={styles.tableWrap}>
              <table className={styles.table} data-testid="pickups">
                <thead>
                  <tr>
                    <th>Household</th>
                    <th>Slot</th>
                    <th>Zone</th>
                    <th>Status</th>
                    <th className={styles.num}>Bags</th>
                    <th>Collector</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={6} className={styles.muted}>No pickups for this day and filter.</td>
                    </tr>
                  )}
                  {data.items.map((p) => (
                    <tr
                      key={p.id}
                      className={styles.rowButton}
                      tabIndex={0}
                      onClick={() => setOpen(p.id)}
                      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setOpen(p.id)}
                    >
                      <td>
                        {p.householdName} {p.isDemo && <span className={styles.tag}>demo</span>}
                      </td>
                      <td>{SLOT_LABELS[p.timeSlot as TimeSlot] ?? p.timeSlot}</td>
                      <td>{ctx.zoneName(p.zone)}</td>
                      <td>
                        <StatusBadge status={p.status as PickupStatus} />
                      </td>
                      <td className={styles.num}>{p.bagCount}</td>
                      <td>{p.collectorName ?? <span className={styles.muted}>Unassigned</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={styles.pager}>
              <span className={styles.muted}>
                {data.total} pickup{data.total === 1 ? "" : "s"} · page {data.page} of {pages}
              </span>
              <div className={styles.controls}>
                <Button variant="secondary" disabled={data.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>
                  Previous
                </Button>
                <Button variant="secondary" disabled={data.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
      {open && <Drawer ctx={ctx} id={open} collectors={collectors} onClose={() => setOpen(null)} onChanged={reload} />}
    </>
  );
}

export default function AdminPickupsPage() {
  return <AdminPage>{(ctx) => <Pickups {...ctx} />}</AdminPage>;
}
