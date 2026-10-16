"use client";

import HouseholdCard from "@/components/resident/HouseholdCard";
import PickupList from "@/components/resident/PickupList";
import ResidentPage, { type ResidentContext } from "@/components/resident/ResidentPage";
import styles from "@/components/resident/resident.module.css";
import SchedulePickupCard from "@/components/resident/SchedulePickupCard";
import { useMyBags, useMyPickups } from "@/lib/liveData";

function Dashboard({ user, profile, household, zoneName }: ResidentContext) {
  const pickups = useMyPickups(user.uid);
  const bags = useMyBags(user.uid);
  return (
    <>
      <div className={styles.pageHeader}>
        <p className={styles.eyebrow}>Resident dashboard</p>
        <h1 className={styles.title} data-testid="dashboard-title">
          Welcome, {profile.name}
        </h1>
        <p className={styles.lead}>Schedule pickups and follow each bag from your door to the warehouse.</p>
      </div>
      <div className={styles.layout}>
        <div className={styles.stack}>
          <HouseholdCard household={household} zoneName={zoneName(household.zone)} bags={bags} pickups={pickups} />
          <SchedulePickupCard user={user} bags={bags} />
        </div>
        <PickupList user={user} pickups={pickups} />
      </div>
    </>
  );
}

export default function ResidentDashboard() {
  return <ResidentPage>{(ctx) => <Dashboard {...ctx} />}</ResidentPage>;
}
