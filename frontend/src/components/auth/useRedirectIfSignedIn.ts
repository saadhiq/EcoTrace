"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { dashboardPath } from "@/lib/roles";

/** On /login and /signup: send an already signed-in user to their dashboard. */
export function useRedirectIfSignedIn(): void {
  const { state } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (state.status === "ready") router.replace(dashboardPath(state.profile.role));
  }, [state, router]);
}
