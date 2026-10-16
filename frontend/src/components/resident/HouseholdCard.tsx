import Card from "@/components/ui/Card";
import type { LiveState } from "@/lib/liveData";
import type { Bag, Household, Pickup } from "@/lib/types";
import { CANCELLABLE } from "@/lib/types";

import styles from "./resident.module.css";

type Props = {
  household: Household;
  zoneName: string;
  bags: LiveState<Bag>;
  pickups: LiveState<Pickup>;
};

export default function HouseholdCard({ household, zoneName, bags, pickups }: Props) {
  const count = <T,>(state: LiveState<T>, keep: (item: T) => boolean) =>
    state.status === "ready" ? state.items.filter(keep).length : "–";

  return (
    <Card title={household.name} subtitle="Your household" data-testid="household-card">
      <dl className={styles.details}>
        <dt>Address</dt>
        <dd>{household.addressLine}</dd>
        <dt>Zone</dt>
        <dd>{zoneName}</dd>
        <dt>Phone</dt>
        <dd>{household.phone}</dd>
      </dl>
      <div className={styles.stats}>
        <div className={styles.stat}>
          <div className={styles.statValue}>{count(bags, (b) => b.status === "issued")}</div>
          <div className={styles.statLabel}>Bags ready</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statValue}>
            {count(pickups, (p) => CANCELLABLE.includes(p.status))}
          </div>
          <div className={styles.statLabel}>Upcoming pickups</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statValue}>
            {count(pickups, (p) => p.status === "processed")}
          </div>
          <div className={styles.statLabel}>Processed</div>
        </div>
      </div>
    </Card>
  );
}
