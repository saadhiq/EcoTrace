"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import ApiStatus from "@/components/ApiStatus";
import { useAuth } from "@/components/auth/AuthProvider";
import { useRedirectIfSignedIn } from "@/components/auth/useRedirectIfSignedIn";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Logo from "@/components/ui/Logo";
import RoleBadge from "@/components/ui/RoleBadge";
import Spinner from "@/components/ui/Spinner";
import { authErrorMessage } from "@/lib/authErrors";
import { ROLE_DESCRIPTIONS, ROLE_LABELS, ROLES, type Role } from "@/lib/roles";

import styles from "../auth.module.css";

export default function LoginPage() {
  useRedirectIfSignedIn();
  const { signIn, signInDemo } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Stays set after success so buttons remain disabled until the redirect.
  const [busy, setBusy] = useState<"form" | Role | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = busy !== null;

  async function run(kind: "form" | Role, action: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(authErrorMessage(err));
      setBusy(null);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void run("form", () => signIn(email.trim(), password));
  }

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <Logo />
        <p className={styles.tagline}>
          Traceable household waste collection — from pickup to Gemini-powered classification.
        </p>
      </div>

      {error && (
        <div className={styles.narrow}>
          <Alert>{error}</Alert>
        </div>
      )}

      <div className={styles.grid}>
        <Card title="Sign in" subtitle="Use your EcoTrace account.">
          <form className={styles.form} onSubmit={onSubmit}>
            <Field
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Field
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" block loading={busy === "form"} disabled={pending}>
              Sign in
            </Button>
            <p className={styles.switch}>
              New here? <Link href="/signup">Create a resident account</Link>
            </p>
          </form>
        </Card>

        <Card
          title="Try a demo account"
          subtitle="One click, no password. Explore EcoTrace as any role."
          data-testid="demo-accounts"
        >
          <div className={styles.demoGrid}>
            {ROLES.map((role) => (
              <button
                key={role}
                type="button"
                className={styles.demoButton}
                disabled={pending}
                onClick={() => void run(role, () => signInDemo(role))}
                data-testid={`demo-${role}`}
              >
                <span className={styles.demoHeader}>
                  <RoleBadge role={role} />
                  {busy === role && <Spinner size={16} />}
                </span>
                <span className={styles.demoDescription}>{ROLE_DESCRIPTIONS[role]}</span>
                <span className={styles.demoCta}>Continue as {ROLE_LABELS[role]} →</span>
              </button>
            ))}
          </div>
          <p className={styles.demoNote}>
            Demo accounts are shared. The demo resident always has sample bags and pickups ready.
          </p>
        </Card>
      </div>

      <footer className={styles.footer}>
        <ApiStatus />
      </footer>
    </div>
  );
}
