"use client";

import { useState } from "react";

import { CATEGORY_ORDER, type CategoryStat } from "@/lib/insights";

import styles from "./insights.module.css";

type Props = {
  categories: Record<string, CategoryStat>;
  total: number;
  label: (id: string) => string;
  /** Whose waste the shares are of, e.g. "your waste" / "all waste". */
  scope?: string;
};

/**
 * Horizontal bars, one per category, in a FIXED order (colour follows the
 * category, never its rank; only validated palette neighbours touch). Every
 * row is directly labelled with name + value, so identity is never colour-alone.
 */
export default function CategoryBreakdown({ categories, total: totalQuantity, label, scope = "your waste" }: Props) {
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const max = Math.max(1, ...CATEGORY_ORDER.map((c) => categories[c]?.quantity ?? 0));
  const total = totalQuantity || 1;

  return (
    <div style={{ position: "relative" }} onMouseLeave={() => setHover(null)}>
      <ul className={styles.bars} data-testid="breakdown" aria-label="Waste by category (item quantity)">
        {CATEGORY_ORDER.map((id) => {
          const stat = categories[id] ?? { items: 0, quantity: 0 };
          const pct = Math.round((stat.quantity / total) * 100);
          const width = stat.quantity ? Math.max(2, (stat.quantity / max) * 100) : 0;
          return (
            <li
              key={id}
              className={styles.bar}
              tabIndex={0}
              aria-label={`${label(id)}: ${stat.quantity} items, ${pct}% of ${scope}`}
              data-category={id}
              data-quantity={stat.quantity}
              onMouseMove={(e) => {
                const box = e.currentTarget.parentElement!.getBoundingClientRect();
                setHover({ id, x: e.clientX - box.left, y: e.currentTarget.offsetTop });
              }}
              onFocus={(e) => setHover({ id, x: e.currentTarget.offsetWidth / 2, y: e.currentTarget.offsetTop })}
              onBlur={() => setHover(null)}
            >
              <span className={styles.barLabel}>
                <span className={styles.swatch} style={{ background: `var(--cat-${id})` }} aria-hidden="true" />
                {label(id)}
              </span>
              <span className={styles.track} aria-hidden="true">
                {width > 0 && <span className={styles.fill} style={{ width: `${width}%`, background: `var(--cat-${id})` }} />}
              </span>
              <span className={`${styles.barValue} ${stat.quantity ? "" : styles.zero}`}>
                {stat.quantity} <span className={styles.small}>{stat.quantity ? `${pct}%` : ""}</span>
              </span>
            </li>
          );
        })}
      </ul>
      {hover && (() => {
        const stat = categories[hover.id] ?? { items: 0, quantity: 0 };
        return (
          <div className={styles.tooltip} style={{ left: hover.x, top: hover.y }} role="tooltip">
            <strong>{label(hover.id)}</strong> · {stat.quantity} item{stat.quantity === 1 ? "" : "s"} ·{" "}
            {Math.round((stat.quantity / total) * 100)}% of {scope}
            {stat.items > 0 && <> · {stat.items} kind{stat.items === 1 ? "" : "s"}</>}
          </div>
        );
      })()}
    </div>
  );
}
