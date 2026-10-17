"use client";

import { useEffect, useState, type FormEvent } from "react";

import AdminPage, { useAdminData } from "@/components/admin/AdminPage";
import styles from "@/components/admin/admin.module.css";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Notice from "@/components/ui/Notice";
import RoleBadge from "@/components/ui/RoleBadge";
import SelectField from "@/components/ui/SelectField";
import Spinner from "@/components/ui/Spinner";
import { adminErrorMessage, createStaff, fetchUsers, type AdminContext } from "@/lib/admin";
import { fetchZones } from "@/lib/resident";
import { ROLE_LABELS, ROLES, type Role } from "@/lib/roles";
import type { Zone } from "@/lib/types";

function StaffForm({ ctx, zones, onCreated }: { ctx: AdminContext; zones: Zone[]; onCreated: () => void }) {
  const [form, setForm] = useState({ email: "", name: "", role: "collector" as "collector" | "operator", zones: [] as string[] });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string; link?: string } | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const created = await createStaff(ctx.user, { ...form, zones: form.role === "collector" ? form.zones : [] });
      setResult({ ok: true, text: `Created ${form.name}. Send them this one-time password setup link:`, link: created.setupLink });
      setForm({ email: "", name: "", role: "collector", zones: [] });
      onCreated();
    } catch (err) {
      setResult({ ok: false, text: adminErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  const toggleZone = (id: string) =>
    setForm((f) => ({ ...f, zones: f.zones.includes(id) ? f.zones.filter((z) => z !== id) : [...f.zones, id] }));

  return (
    <Card title="Add staff" subtitle="Creates a collector or warehouse operator account with a one-time password setup link.">
      <form className={styles.form} onSubmit={(e) => void submit(e)} data-testid="staff-form">
        <Field label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Field label="Email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <SelectField
          label="Role"
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value as "collector" | "operator" })}
          options={[
            { value: "collector", label: ROLE_LABELS.collector },
            { value: "operator", label: ROLE_LABELS.operator },
          ]}
        />
        {form.role === "collector" && (
          <fieldset>
            <legend className={styles.tileLabel}>Zones covered</legend>
            <div className={styles.zoneChecks}>
              {zones.map((z) => (
                <label key={z.id}>
                  <input type="checkbox" checked={form.zones.includes(z.id)} onChange={() => toggleZone(z.id)} />
                  {z.name}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <Button type="submit" loading={busy} disabled={form.role === "collector" && form.zones.length === 0}>
          Create account
        </Button>
        {ctx.isDemo && <p className={styles.muted}>The public demo admin can&apos;t create accounts; try it to see the guard.</p>}
        {result &&
          (result.ok ? (
            <Notice>
              {result.text} <span className={styles.key}>{result.link}</span>
            </Notice>
          ) : (
            <Alert>{result.text}</Alert>
          ))}
      </form>
    </Card>
  );
}

function People(ctx: AdminContext) {
  const [role, setRole] = useState<Role | "">("");
  const [zones, setZones] = useState<Zone[]>([]);
  const { data, error, reload } = useAdminData(() => fetchUsers(ctx.user, role || undefined), [role]);
  useEffect(() => {
    fetchZones().then(setZones).catch(() => undefined);
  }, []);

  return (
    <>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>People</h1>
          <p className={styles.muted}>Accounts by role. Roles are Firebase Auth custom claims, mirrored in Firestore.</p>
        </div>
        <SelectField
          label="Role"
          value={role}
          onChange={(e) => setRole(e.target.value as Role | "")}
          options={[{ value: "", label: "All roles" }, ...ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] }))]}
        />
      </div>
      <div className={styles.grid2}>
        <Card title={`${data?.length ?? "…"} accounts`}>
          {error ? <Alert>{adminErrorMessage(error)}</Alert> : null}
          {!data && !error && <Spinner />}
          {data && (
            <div className={styles.tableWrap}>
              <table className={styles.table} data-testid="users">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Zones</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((u) => (
                    <tr key={u.uid}>
                      <td>
                        {u.name} {u.isSynthetic && <span className={styles.tag}>synthetic</span>}
                        <div className={styles.muted}>{u.email ?? ""}</div>
                      </td>
                      <td>
                        <RoleBadge role={u.role} />
                      </td>
                      <td>{u.zones.length ? u.zones.map((z) => ctx.zoneName(z)).join(", ") : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <StaffForm ctx={ctx} zones={zones} onCreated={reload} />
      </div>
    </>
  );
}

export default function AdminPeoplePage() {
  return <AdminPage>{(ctx) => <People {...ctx} />}</AdminPage>;
}
