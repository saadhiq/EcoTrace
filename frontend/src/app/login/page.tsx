"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import ApiStatus from "@/components/ApiStatus";
import { useAuth } from "@/components/auth/AuthProvider";
import DemoSignIn from "@/components/auth/DemoSignIn";
import { useRedirectIfSignedIn } from "@/components/auth/useRedirectIfSignedIn";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Logo from "@/components/ui/Logo";
import { authErrorMessage } from "@/lib/authErrors";

import styles from "../auth.module.css";

export default function LoginPage() {
  useRedirectIfSignedIn();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Stays set after success so the form remains disabled until the redirect.
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = busy || demoBusy;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
    } catch (err) {
      setError(authErrorMessage(err));
      setBusy(false);
    }
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
          <form className={styles.form} onSubmit={(e) => void onSubmit(e)}>
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
            <Button type="submit" block loading={busy} disabled={pending}>
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
          <DemoSignIn disabled={busy} onBusyChange={setDemoBusy} />
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
