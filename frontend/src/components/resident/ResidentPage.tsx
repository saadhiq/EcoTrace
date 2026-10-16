"use client";

import type { User } from "firebase/auth";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import RoleGuard from "@/components/auth/RoleGuard";
import AppShell, { type NavItem } from "@/components/ui/AppShell";
import ErrorState from "@/components/ui/ErrorState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import { fetchMyHousehold, fetchZones, residentErrorMessage } from "@/lib/resident";
import type { Profile } from "@/lib/roles";
import type { Household, Zone } from "@/lib/types";

import OnboardingForm from "./OnboardingForm";

export const RESIDENT_NAV: NavItem[] = [
  { href: "/resident", label: "Dashboard" },
  { href: "/resident/bags", label: "My bags" },
];

export type ResidentContext = {
  user: User;
  profile: Profile;
  household: Household;
  zones: Zone[];
  zoneName: (id: string) => string;
};

type Load =
  | { status: "loading" }
  | { status: "none" }
  | { status: "ready"; household: Household }
  | { status: "error"; message: string };

function ResidentContent({
  user,
  profile,
  children,
}: {
  user: User;
  profile: Profile;
  children: (ctx: ResidentContext) => ReactNode;
}) {
  const { logout } = useAuth();
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [zones, setZones] = useState<Zone[]>([]);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    fetchZones()
      .then((z) => active && setZones(z))
      .catch(() => undefined); // Zone names fall back to ids.
    fetchMyHousehold(user)
      .then((h) => active && setLoad(h ? { status: "ready", household: h } : { status: "none" }))
      .catch((err: unknown) => active && setLoad({ status: "error", message: residentErrorMessage(err) }));
    return () => {
      active = false;
    };
  }, [user, attempt]);

  const retry = useCallback(() => {
    setLoad({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const zoneName = useCallback((id: string) => zones.find((z) => z.id === id)?.name ?? id, [zones]);

  return (
    <AppShell profile={profile} nav={load.status === "ready" ? RESIDENT_NAV : undefined}>
      {load.status === "loading" && <FullPageSpinner />}
      {load.status === "error" && (
        <ErrorState message={load.message} onRetry={retry} onLogout={() => void logout()} />
      )}
      {load.status === "none" && (
        <OnboardingForm
          user={user}
          defaultName={profile.name}
          zones={zones}
          onCreated={(household) => setLoad({ status: "ready", household })}
        />
      )}
      {load.status === "ready" &&
        children({ user, profile, household: load.household, zones, zoneName })}
    </AppShell>
  );
}

/** Resident-only page: guard, top bar, household loading and first-time onboarding. */
export default function ResidentPage({ children }: { children: (ctx: ResidentContext) => ReactNode }) {
  const { state } = useAuth();
  return (
    <RoleGuard role="resident">
      {(profile) =>
        state.status === "ready" ? (
          <ResidentContent user={state.user} profile={profile}>
            {children}
          </ResidentContent>
        ) : null
      }
    </RoleGuard>
  );
}
