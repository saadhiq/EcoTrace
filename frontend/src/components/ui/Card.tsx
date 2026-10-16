import type { HTMLAttributes, ReactNode } from "react";

import styles from "./ui.module.css";

type Props = HTMLAttributes<HTMLElement> & {
  title?: ReactNode;
  subtitle?: ReactNode;
};

export default function Card({ title, subtitle, className, children, ...rest }: Props) {
  return (
    <section className={[styles.card, className].filter(Boolean).join(" ")} {...rest}>
      {title && <h2 className={styles.cardTitle}>{title}</h2>}
      {subtitle && <p className={styles.cardSubtitle}>{subtitle}</p>}
      {children}
    </section>
  );
}
