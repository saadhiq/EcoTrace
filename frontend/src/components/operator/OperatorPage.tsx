"use client";

import type { User } from "firebase/auth";
import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import RoleGuard from "@/components/auth/RoleGuard";
import AppShell, { type NavItem } from "@/components/ui/AppShell";
import { fetchTaxonomy, type Taxonomy } from "@/lib/operator";
import { fetchZones } from "@/lib/resident";
import type { Profile } from "@/lib/roles";
import type { Zone } from "@/lib/types";

export const OPERATOR_NAV: NavItem[] = [{ href: "/operator", label: "Warehouse queue" }];

export type OperatorContext = {
  user: User;
  profile: Profile;
  taxonomy: Taxonomy | null;
  zoneName: (id: string | null) => string;
};

function Content({ user, profile, children }: { user: User; profile: Profile; children: (ctx: OperatorContext) => ReactNode }) {
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  useEffect(() => {
    fetchTaxonomy().then(setTaxonomy).catch(() => undefined);
    fetchZones().then(setZones).catch(() => undefined);
  }, []);
  const zoneName = (id: string | null) => (id ? (zones.find((z) => z.id === id)?.name ?? id) : "—");
  return (
    <AppShell profile={profile} nav={OPERATOR_NAV}>
      {children({ user, profile, taxonomy, zoneName })}
    </AppShell>
  );
}

/** Operator-only page: guard, top bar, shared taxonomy + zone names. */
export default function OperatorPage({ children }: { children: (ctx: OperatorContext) => ReactNode }) {
  const { state } = useAuth();
  return (
    <RoleGuard role="operator">
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
