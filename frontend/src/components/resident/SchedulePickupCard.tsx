"use client";

import type { User } from "firebase/auth";
import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";

import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import Field from "@/components/ui/Field";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import Notice from "@/components/ui/Notice";
import TextareaField from "@/components/ui/TextareaField";
import { formatDay, pickupWindow } from "@/lib/dates";
import type { LiveState } from "@/lib/liveData";
import { residentErrorMessage, schedulePickup } from "@/lib/resident";
import { SLOT_LABELS, type Bag, type TimeSlot } from "@/lib/types";

import styles from "./resident.module.css";

const MAX_BAGS = 5;

export default function SchedulePickupCard({ user, bags }: { user: User; bags: LiveState<Bag> }) {
  const range = useMemo(() => pickupWindow(), []);
  const [date, setDate] = useState(range.min);
  const [timeSlot, setTimeSlot] = useState<TimeSlot>("morning");
  const [selected, setSelected] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const issued = bags.status === "ready" ? bags.items.filter((b) => b.status === "issued") : [];
  // Drop selections that are no longer available (e.g. booked in another tab).
  const chosen = selected.filter((code) => issued.some((b) => b.code === code));

  function toggle(code: string) {
    setSelected((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code].slice(0, MAX_BAGS),
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (chosen.length === 0) {
      setError("Choose at least one bag.");
      return;
    }
    setBusy(true);
    try {
      await schedulePickup(user, { date, timeSlot, bagCodes: chosen, notes: notes.trim() });
      setSuccess(
        `Pickup requested for ${formatDay(date)} (${timeSlot}) with ${chosen.length} bag${chosen.length > 1 ? "s" : ""}.`,
      );
      setSelected([]);
      setNotes("");
    } catch (err) {
      setError(residentErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Schedule a pickup" subtitle="Choose a day, a time slot and the bags to collect." data-testid="schedule-card">
      <form className={styles.form} onSubmit={(e) => void onSubmit(e)}>
        {error && <Alert>{error}</Alert>}
        {success && <Notice>{success}</Notice>}

        <div className={styles.row}>
          <Field
            label="Date"
            type="date"
            required
            min={range.min}
            max={range.max}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            data-testid="pickup-date"
          />
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>Time slot</legend>
            <div className={styles.choices}>
              {(Object.keys(SLOT_LABELS) as TimeSlot[]).map((slot) => (
                <label key={slot} className={styles.choice}>
                  <input
                    type="radio"
                    name="timeSlot"
                    value={slot}
                    checked={timeSlot === slot}
                    onChange={() => setTimeSlot(slot)}
                  />
                  {slot === "morning" ? "Morning" : "Afternoon"}
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        <fieldset className={styles.fieldset}>
          <legend className={styles.legend}>
            Bags <span className={styles.legendHint}>({chosen.length}/{MAX_BAGS} selected)</span>
          </legend>
          {bags.status === "loading" && <FullPageSpinner />}
          {bags.status === "error" && <Alert>{bags.message}</Alert>}
          {bags.status === "ready" && issued.length === 0 && (
            <EmptyState title="No bags ready">
              <span>
                All your bags are in use. <Link href="/resident/bags">Request more bags</Link>
              </span>
            </EmptyState>
          )}
          {issued.length > 0 && (
            <div className={styles.choices} data-testid="bag-checklist">
              {issued.map((bag) => {
                const checked = chosen.includes(bag.code);
                return (
                  <label key={bag.code} className={styles.choice}>
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!checked && chosen.length >= MAX_BAGS}
                      onChange={() => toggle(bag.code)}
                    />
                    <span className={styles.code}>{bag.code}</span>
                  </label>
                );
              })}
            </div>
          )}
        </fieldset>

        <TextareaField
          label="Notes for the collector (optional)"
          maxLength={280}
          hint={`${notes.length}/280`}
          placeholder="e.g. Bags are by the side gate."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />

        <Button type="submit" block loading={busy} disabled={issued.length === 0}>
          Request pickup
        </Button>
      </form>
    </Card>
  );
}
