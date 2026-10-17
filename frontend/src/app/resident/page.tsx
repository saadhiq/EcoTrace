"use client";

import HouseholdCard from "@/components/resident/HouseholdCard";
import InsightsSection from "@/components/resident/insights/InsightsSection";
import PrivacyCard from "@/components/resident/insights/PrivacyCard";
import SwapsCard from "@/components/resident/insights/SwapsCard";
import TipsCard from "@/components/resident/insights/TipsCard";
import PickupList from "@/components/resident/PickupList";
import ResidentPage, { type ResidentContext } from "@/components/resident/ResidentPage";
import styles from "@/components/resident/resident.module.css";
import SchedulePickupCard from "@/components/resident/SchedulePickupCard";
import { useState } from "react";

import { useHouseholdStats } from "@/lib/insights";
import { useMyBags, useMyPickups } from "@/lib/liveData";

function Dashboard({ user, profile, household, zoneName }: ResidentContext) {
  const pickups = useMyPickups(user.uid);
  const bags = useMyBags(user.uid);
  const stats = useHouseholdStats(user.uid);
  // Bumped when consent changes so the swaps card re-checks access.
  const [consentKey, setConsentKey] = useState(0);
  const statsHash = stats.status === "ready" ? (stats.value?.statsHash ?? null) : null;
  return (
    <>
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Resident dashboard</p>
        <h1 className={styles.title} data-testid="dashboard-title">
          Welcome, {profile.name}
        </h1>
        <p className={styles.lead}>Schedule pickups and follow each bag from your door to the warehouse.</p>
      </div>
      <InsightsSection uid={user.uid} statsState={stats} />
      <div style={{ marginBottom: 24 }}>
        <SwapsCard user={user} consentKey={consentKey} statsHash={statsHash} />
      </div>
      <div className={styles.layout}>
        <div className={styles.stack}>
          <HouseholdCard household={household} zoneName={zoneName(household.zone)} bags={bags} pickups={pickups} />
          <SchedulePickupCard user={user} bags={bags} />
        </div>
        <PickupList user={user} pickups={pickups} />
      </div>
      <div className={styles.layout} style={{ marginTop: 24 }}>
        <TipsCard user={user} statsHash={statsHash} />
        <PrivacyCard user={user} onChange={() => setConsentKey((k) => k + 1)} />
      </div>
    </>
  );
}

export default function ResidentDashboard() {
  return <ResidentPage>{(ctx) => <Dashboard {...ctx} />}</ResidentPage>;
}
