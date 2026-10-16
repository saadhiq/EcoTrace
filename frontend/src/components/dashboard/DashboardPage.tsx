"use client";

import RoleGuard from "@/components/auth/RoleGuard";
import AppShell from "@/components/ui/AppShell";
import Card from "@/components/ui/Card";
import { ROLE_DESCRIPTIONS, ROLE_LABELS, type Role } from "@/lib/roles";

import styles from "./dashboard.module.css";

export type ComingSoonItem = { title: string; description: string };

type Props = {
  role: Role;
  comingSoon: ComingSoonItem[];
};

/** Guarded placeholder dashboard shared by every role until features land. */
export default function DashboardPage({ role, comingSoon }: Props) {
  return (
    <RoleGuard role={role}>
      {(profile) => (
        <AppShell profile={profile}>
          <div className={styles.header}>
            <div>
              <p className={styles.eyebrow}>{ROLE_LABELS[role]} dashboard</p>
              <h1 className={styles.title} data-testid="dashboard-title">
                Welcome, {profile.name}
              </h1>
              <p className={styles.lead}>{ROLE_DESCRIPTIONS[role]}</p>
            </div>
          </div>

          <div className={styles.grid}>
            {comingSoon.map((item) => (
              <Card key={item.title} className={styles.tile}>
                <span className={styles.soon}>Coming soon</span>
                <h2 className={styles.tileTitle}>{item.title}</h2>
                <p className={styles.tileText}>{item.description}</p>
              </Card>
            ))}
          </div>
        </AppShell>
      )}
    </RoleGuard>
  );
}
