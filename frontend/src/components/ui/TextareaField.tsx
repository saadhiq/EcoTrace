import { useId, type TextareaHTMLAttributes } from "react";

import styles from "./ui.module.css";

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; hint?: string };

export default function TextareaField({ label, hint, id, ...rest }: Props) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <textarea id={inputId} className={`${styles.input} ${styles.textarea}`} {...rest} />
      {hint && <span className={styles.hint}>{hint}</span>}
    </div>
  );
}
