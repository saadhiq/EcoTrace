"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import Alert from "@/components/ui/Alert";
import RoleBadge from "@/components/ui/RoleBadge";
import Spinner from "@/components/ui/Spinner";
import { authErrorMessage } from "@/lib/authErrors";
import { dashboardPath, ROLE_DESCRIPTIONS, ROLE_LABELS, ROLES, type Role } from "@/lib/roles";

import styles from "./DemoSignIn.module.css";

type Props = {
  /** Per-role text under the badge (defaults to the role descriptions). */
  descriptions?: Partial<Record<Role, string>>;
  /** Disable the buttons from outside (e.g. while the login form is submitting). */
  disabled?: boolean;
  /** Told when a demo sign-in starts (true) or fails (false). */
  onBusyChange?: (busy: boolean) => void;
};

/** The one-click demo sign-in buttons (custom-token flow), shared by /login and the landing page. */
export default function DemoSignIn({ descriptions, disabled = false, onBusyChange }: Props) {
  const { signInDemo } = useAuth();
  const router = useRouter();
  // Stays set after success so the buttons remain disabled until the dashboard loads.
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start(role: Role) {
    setBusy(role);
    setError(null);
    onBusyChange?.(true);
    try {
      await signInDemo(role);
      router.replace(dashboardPath(role));
    } catch (err) {
      setError(authErrorMessage(err));
      setBusy(null);
      onBusyChange?.(false);
    }
  }

  return (
    <div className={styles.wrap}>
      {error && <Alert>{error}</Alert>}
      <div className={styles.grid}>
        {ROLES.map((role) => (
          <button
            key={role}
            type="button"
            className={styles.button}
            disabled={disabled || busy !== null}
            onClick={() => void start(role)}
            data-testid={`demo-${role}`}
          >
            <span className={styles.header}>
              <RoleBadge role={role} />
              {busy === role && <Spinner size={16} />}
            </span>
            <span className={styles.description}>{descriptions?.[role] ?? ROLE_DESCRIPTIONS[role]}</span>
            <span className={styles.cta}>Continue as {ROLE_LABELS[role]} →</span>
          </button>
        ))}
      </div>
    </div>
  );
}
