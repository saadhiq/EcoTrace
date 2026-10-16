import { STATUS_LABELS, type BagStatus, type PickupStatus } from "@/lib/types";

import styles from "./ui.module.css";

export default function StatusBadge({ status }: { status: BagStatus | PickupStatus }) {
  return (
    <span className={`${styles.status} ${styles[`status-${status}`] ?? ""}`} data-status={status}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
