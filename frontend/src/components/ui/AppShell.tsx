"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { dashboardPath, type Profile } from "@/lib/roles";

import Button from "./Button";
import Logo from "./Logo";
import RoleBadge from "./RoleBadge";
import styles from "./ui.module.css";

export type NavItem = { href: string; label: string };

function normalise(path: string): string {
  return path.replace(/\/+$/, "") || "/";
}

/** Top bar (app name, user, role badge, logout), optional sub-nav, content column. */
export default function AppShell({
  profile,
  nav,
  children,
}: {
  profile: Profile;
  nav?: NavItem[];
  children: ReactNode;
}) {
  const { logout } = useAuth();
  const pathname = normalise(usePathname() ?? "/");
  return (
    <>
      <header className={styles.topbar} data-print="hide">
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
      {nav && nav.length > 0 && (
        <nav className={styles.subnav} aria-label="Sections" data-print="hide">
          <div className={styles.subnavInner}>
            {nav.map((item) => {
              const active = normalise(item.href) === pathname;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`${styles.subnavLink} ${active ? styles.subnavActive : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
      <main className={styles.main}>{children}</main>
    </>
  );
}
