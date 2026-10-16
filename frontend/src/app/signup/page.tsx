"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { useRedirectIfSignedIn } from "@/components/auth/useRedirectIfSignedIn";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Logo from "@/components/ui/Logo";
import { authErrorMessage } from "@/lib/authErrors";

import styles from "../auth.module.css";

export default function SignupPage() {
  useRedirectIfSignedIn();
  const { signUp } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signUp(name.trim(), email.trim(), password);
    } catch (err) {
      setError(authErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <Logo />
        <p className={styles.tagline}>Create a resident account to schedule pickups.</p>
      </div>

      <div className={styles.narrow}>
        <Card title="Create your account" subtitle="Staff accounts are created by an admin.">
          <form className={styles.form} onSubmit={(e) => void onSubmit(e)}>
            {error && <Alert>{error}</Alert>}
            <Field
              label="Full name"
              autoComplete="name"
              required
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
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
              autoComplete="new-password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" block loading={busy}>
              Create account
            </Button>
            <p className={styles.switch}>
              Already have an account? <Link href="/login">Sign in</Link>
            </p>
          </form>
        </Card>
      </div>
    </div>
  );
}
