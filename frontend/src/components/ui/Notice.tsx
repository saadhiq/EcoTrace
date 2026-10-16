import type { ReactNode } from "react";

import styles from "./ui.module.css";

/** Positive/neutral inline message (success confirmations). */
export default function Notice({ children }: { children: ReactNode }) {
  return (
    <div role="status" className={styles.notice}>
      {children}
    </div>
  );
}
