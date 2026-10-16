import type { ReactNode } from "react";

import styles from "./ui.module.css";

export default function Alert({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className={styles.alert}>
      {children}
    </div>
  );
}
