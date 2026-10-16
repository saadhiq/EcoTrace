"use client";

import type { ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { dashboardPath, type Profile } from "@/lib/roles";

import Button from "./Button";
import Logo from "./Logo";
import RoleBadge from "./RoleBadge";
import styles from "./ui.module.css";

/** Top bar (app name, user, role badge, logout) + centred content column. */
export default function AppShell({ profile, children }: { profile: Profile; children: ReactNode }) {
  const { logout } = useAuth();
  return (
    <>
      <header className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Logo href={dashboardPath(profile.role)} />
          <div className={styles.userArea}>
            <span className={styles.userName} title={profile.email ?? undefined}>
              {profile.name}
            </span>
            <RoleBadge role={profile.role} />
            <Button variant="ghost" onClick={() => void logout()}>
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className={styles.main}>{children}</main>
    </>
  );
}
