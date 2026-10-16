import { ROLE_LABELS, type Role } from "@/lib/roles";

import styles from "./ui.module.css";

export default function RoleBadge({ role }: { role: Role }) {
  return (
    <span className={`${styles.badge} ${styles[`role-${role}`]}`} data-role={role}>
      {ROLE_LABELS[role]}
    </span>
  );
}
