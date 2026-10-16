"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import { dashboardPath } from "@/lib/roles";

/** Sends the visitor to their dashboard, or to /login. */
export default function Home() {
  const { state } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (state.status === "ready") router.replace(dashboardPath(state.profile.role));
    else if (state.status === "signedOut" || state.status === "error") router.replace("/login");
  }, [state, router]);

  return <FullPageSpinner />;
}
