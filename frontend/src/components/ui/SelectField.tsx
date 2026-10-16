import { useId, type SelectHTMLAttributes } from "react";

import styles from "./ui.module.css";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: { value: string; label: string }[];
  placeholder?: string;
};

export default function SelectField({ label, options, placeholder, id, ...rest }: Props) {
  const generated = useId();
  const selectId = id ?? generated;
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={selectId}>
        {label}
      </label>
      <select id={selectId} className={`${styles.input} ${styles.select}`} {...rest}>
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
