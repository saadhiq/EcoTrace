"use client";

import type { User } from "firebase/auth";
import { useState, type FormEvent } from "react";

import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import SelectField from "@/components/ui/SelectField";
import { createHousehold, residentErrorMessage } from "@/lib/resident";
import type { Household, Zone } from "@/lib/types";

import styles from "./resident.module.css";

type Props = {
  user: User;
  defaultName: string;
  zones: Zone[];
  onCreated: (household: Household) => void;
};

export default function OnboardingForm({ user, defaultName, zones, onCreated }: Props) {
  const [name, setName] = useState(defaultName ? `${defaultName}'s household` : "");
  const [phone, setPhone] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [zone, setZone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const household = await createHousehold(user, {
        name: name.trim(),
        phone: phone.trim(),
        addressLine: addressLine.trim(),
        zone,
      });
      onCreated(household);
    } catch (err) {
      setError(residentErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div className={styles.narrow} data-testid="onboarding">
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Welcome to EcoTrace</p>
        <h1 className={styles.title}>Set up your household</h1>
        <p className={styles.lead}>
          We&apos;ll issue your first 5 bags with QR codes as soon as you&apos;re set up.
        </p>
      </div>
      <Card>
        <form className={styles.form} onSubmit={(e) => void onSubmit(e)}>
          {error && <Alert>{error}</Alert>}
          <Field
            label="Household name"
            required
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Field
            label="Phone"
            type="tel"
            autoComplete="tel"
            required
            placeholder="+94 77 123 4567"
            pattern="^\+?[0-9][0-9 \-]{6,18}$"
            title="Digits, spaces or dashes, optionally starting with +"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <Field
            label="Address"
            autoComplete="street-address"
            required
            maxLength={200}
            placeholder="House number and street"
            value={addressLine}
            onChange={(e) => setAddressLine(e.target.value)}
          />
          <SelectField
            label="Zone"
            required
            placeholder={zones.length ? "Choose your area" : "Loading zones…"}
            options={zones.map((z) => ({ value: z.id, label: z.name }))}
            value={zone}
            onChange={(e) => setZone(e.target.value)}
          />
          <Button type="submit" block loading={busy} disabled={!zones.length}>
            Create household
          </Button>
        </form>
      </Card>
    </div>
  );
}
