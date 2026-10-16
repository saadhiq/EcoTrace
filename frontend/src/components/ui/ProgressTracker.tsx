import { PICKUP_STEPS, STATUS_LABELS, type PickupStatus } from "@/lib/types";

import styles from "./ui.module.css";

const STEP_LABELS: Record<(typeof PICKUP_STEPS)[number], string> = {
  requested: "Requested",
  assigned: "Assigned",
  collected: "Collected",
  delivered: "Delivered",
  processed: "Processed",
};

/** requested → assigned → collected → delivered → processed. */
export default function ProgressTracker({ status }: { status: PickupStatus }) {
  const current = PICKUP_STEPS.indexOf(status as (typeof PICKUP_STEPS)[number]);
  return (
    <ol className={styles.tracker} aria-label={`Pickup progress: ${STATUS_LABELS[status]}`}>
      {PICKUP_STEPS.map((step, i) => {
        const state = i < current || status === "processed" ? "done" : i === current ? "current" : "todo";
        const cls = state === "done" ? styles.stepDone : state === "current" ? styles.stepCurrent : "";
        return (
          <li
            key={step}
            className={`${styles.step} ${cls}`}
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className={styles.dot} aria-hidden="true" />
            {STEP_LABELS[step]}
          </li>
        );
      })}
    </ol>
  );
}
