"use client";

import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import RoleGuard from "@/components/auth/RoleGuard";
import AppShell, { type NavItem } from "@/components/ui/AppShell";
import type { AdminContext } from "@/lib/admin";
import { fetchZones } from "@/lib/resident";
import type { Zone } from "@/lib/types";

import styles from "./admin.module.css";

export const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/ai-quality", label: "AI quality" },
  { href: "/admin/pickups", label: "Pickups" },
  { href: "/admin/people", label: "People" },
  { href: "/admin/partners", label: "Partners" },
];

function Content({ ctx, children }: { ctx: Omit<AdminContext, "zoneName">; children: (ctx: AdminContext) => ReactNode }) {
  const [zones, setZones] = useState<Zone[]>([]);
  useEffect(() => {
    fetchZones().then(setZones).catch(() => undefined);
  }, []);
  const zoneName = (id: string | null) => (id ? (zones.find((z) => z.id === id)?.name ?? id) : "—");
  return (
    <AppShell profile={ctx.profile} nav={ADMIN_NAV}>
      <div className={styles.stack}>
        {ctx.isDemo && (
          <div className={styles.banner} role="note" data-testid="demo-banner">
            Public demo: read-only for accounts and partners.
          </div>
        )}
        {children({ ...ctx, zoneName })}
      </div>
    </AppShell>
  );
}

/** Admin-only page: guard, top bar + section nav, demo banner, zone names. */
export default function AdminPage({ children }: { children: (ctx: AdminContext) => ReactNode }) {
  const { state } = useAuth();
  return (
    <RoleGuard role="admin">
      {(profile) =>
        state.status === "ready" ? (
          <Content ctx={{ user: state.user, profile, isDemo: Boolean(profile.isDemo) }}>{children}</Content>
        ) : null
      }
    </RoleGuard>
  );
}

export function Tile({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className={styles.tile}>
      <span className={styles.tileLabel}>{label}</span>
      <span className={styles.tileValue}>{value}</span>
      {note && <span className={styles.tileNote}>{note}</span>}
    </div>
  );
}

/** Fetch-on-deps helper with loading/error state. */
export function useAdminData<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    load()
      .then((d) => {
        if (!live) return;
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, reload: () => setTick((t) => t + 1), setData };
}
