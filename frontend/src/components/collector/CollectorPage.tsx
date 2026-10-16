"use client";

import type { User } from "firebase/auth";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import RoleGuard from "@/components/auth/RoleGuard";
import AppShell, { type NavItem } from "@/components/ui/AppShell";
import { fetchZones } from "@/lib/resident";
import type { Profile } from "@/lib/roles";
import type { Zone } from "@/lib/types";

export const COLLECTOR_NAV: NavItem[] = [
  { href: "/collector", label: "Today" },
  { href: "/collector/handover", label: "Warehouse handover" },
];

export type CollectorContext = {
  user: User;
  profile: Profile;
  zoneName: (id: string) => string;
};

function Content({ user, profile, children }: { user: User; profile: Profile; children: (ctx: CollectorContext) => ReactNode }) {
  const [zones, setZones] = useState<Zone[]>([]);
  useEffect(() => {
    fetchZones().then(setZones).catch(() => undefined); // names fall back to ids
  }, []);
  const zoneName = useCallback((id: string) => zones.find((z) => z.id === id)?.name ?? id, [zones]);
  return (
    <AppShell profile={profile} nav={COLLECTOR_NAV}>
      {children({ user, profile, zoneName })}
    </AppShell>
  );
}

/** Collector-only page: guard, top bar with Today / Handover tabs. */
export default function CollectorPage({ children }: { children: (ctx: CollectorContext) => ReactNode }) {
  const { state } = useAuth();
  return (
    <RoleGuard role="collector">
      {(profile) =>
        state.status === "ready" ? (
          <Content user={state.user} profile={profile}>
            {children}
          </Content>
        ) : null
      }
    </RoleGuard>
  );
}
