import styles from "./ui.module.css";

/** Category chip: colored dot carries identity; the label stays in text ink. */
export default function CategoryChip({ category, label }: { category: string; label: string }) {
  return (
    <span
      className={styles.catChip}
      style={
        {
          "--chip-color": `var(--cat-${category}, var(--cat-other))`,
          background: `var(--cat-${category}-soft, var(--cat-other-soft))`,
        } as React.CSSProperties
      }
      data-category={category}
    >
      {label}
    </span>
  );
}
