import styles from "./ui.module.css";

/** Colored chip for a waste category (colors from --cat-* tokens). */
export default function CategoryChip({ category, label }: { category: string; label: string }) {
  return (
    <span
      className={styles.catChip}
      style={{ color: `var(--cat-${category}, var(--cat-other))`, background: `var(--cat-${category}-soft, var(--cat-other-soft))` }}
      data-category={category}
    >
      {label}
    </span>
  );
}
