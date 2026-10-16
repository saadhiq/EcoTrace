"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import ErrorState from "@/components/ui/ErrorState";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import { dashboardPath, type Profile, type Role } from "@/lib/roles";

/**
 * Renders children only for a signed-in user with `role`.
 * Signed-out users go to /login; other roles go to their own dashboard.
 */
export default function RoleGuard({
  role,
  children,
}: {
  role: Role;
  children: (profile: Profile) => ReactNode;
}) {
  const { state, retry, logout } = useAuth();
  const router = useRouter();

  const redirect =
    state.status === "signedOut"
      ? "/login"
      : state.status === "ready" && state.profile.role !== role
        ? dashboardPath(state.profile.role)
        : null;

  useEffect(() => {
    if (redirect) router.replace(redirect);
  }, [redirect, router]);

  if (state.status === "error") {
    return <ErrorState message={state.message} onRetry={retry} onLogout={logout} />;
  }
  if (state.status === "ready" && !redirect) return <>{children(state.profile)}</>;
  return <FullPageSpinner />;
}
