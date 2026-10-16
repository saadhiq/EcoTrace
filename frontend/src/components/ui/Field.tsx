import { useId, type InputHTMLAttributes } from "react";

import styles from "./ui.module.css";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string };

export default function Field({ label, id, ...rest }: Props) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <input id={inputId} className={styles.input} {...rest} />
    </div>
  );
}
