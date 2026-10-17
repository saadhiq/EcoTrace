"use client";

import Button from "@/components/ui/Button";
import CategoryChip from "@/components/ui/CategoryChip";
import { LOW_CONFIDENCE, type Option, type WasteItem } from "@/lib/operator";

import styles from "./operator.module.css";

export type Row = WasteItem & {
  key: string;
  /** Index of the AI item this row came from; null = added by the operator. */
  aiIndex: number | null;
  confidence: number | null;
};

let nextKey = 0;
export const newRowKey = () => `row-${++nextKey}`;

export function emptyRow(): Row {
  return {
    key: newRowKey(),
    aiIndex: null,
    confidence: null,
    name: "",
    category: "other",
    material: "",
    productType: "",
    brand: null,
    quantity: 1,
    recyclable: false,
  };
}

type Props = {
  rows: Row[];
  categories: Option[];
  onChange: (rows: Row[]) => void;
  disabled?: boolean;
};

/** Editable list of bag items: category chips, quantity, recyclable, add/delete. */
export default function ItemEditor({ rows, categories, onChange, disabled = false }: Props) {
  const label = (id: string) => categories.find((c) => c.id === id)?.label ?? id;
  const update = (key: string, patch: Partial<Row>) =>
    onChange(rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));

  return (
    <div>
      <ul className={styles.items} data-testid="item-editor">
        {rows.map((row) => {
          const low = row.confidence !== null && row.confidence < LOW_CONFIDENCE;
          return (
            <li
              key={row.key}
              className={`${styles.item} ${low ? styles.itemLow : ""}`}
              data-testid="item-row"
              data-low={low}
              data-category={row.category}
            >
              <div className={styles.itemMain}>
                <input
                  className={styles.input}
                  aria-label="Item name"
                  placeholder="Item name"
                  maxLength={80}
                  value={row.name}
                  disabled={disabled}
                  onChange={(e) => update(row.key, { name: e.target.value })}
                  data-testid="item-name"
                />
                <select
                  className={`${styles.input} ${styles.catSelect}`}
                  aria-label="Category"
                  value={row.category}
                  disabled={disabled}
                  onChange={(e) => update(row.key, { category: e.target.value })}
                  style={{
                    color: "var(--color-text)",
                    borderColor: `var(--cat-${row.category})`,
                    background: `var(--cat-${row.category}-soft)`,
                  }}
                  data-testid="item-category"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <input
                  className={styles.input}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={999}
                  aria-label="Quantity"
                  value={row.quantity}
                  disabled={disabled}
                  onChange={(e) => update(row.key, { quantity: Math.max(1, Math.min(999, Number(e.target.value) || 1)) })}
                  data-testid="item-qty"
                />
                <label className={styles.toggle}>
                  <input
                    type="checkbox"
                    checked={row.recyclable}
                    disabled={disabled}
                    onChange={(e) => update(row.key, { recyclable: e.target.checked })}
                    data-testid="item-recyclable"
                  />
                  Recyclable
                </label>
              </div>
              <div className={styles.rowTop}>
                <button
                  type="button"
                  className={styles.iconButton}
                  aria-label={`Delete ${row.name || "item"}`}
                  disabled={disabled}
                  onClick={() => onChange(rows.filter((r) => r.key !== row.key))}
                  data-testid="item-delete"
                >
                  ×
                </button>
              </div>
              <div className={styles.itemDetails}>
                <input
                  className={`${styles.input} ${styles.inputSmall}`}
                  aria-label="Material"
                  placeholder="Material"
                  maxLength={60}
                  value={row.material}
                  disabled={disabled}
                  onChange={(e) => update(row.key, { material: e.target.value })}
                />
                <input
                  className={`${styles.input} ${styles.inputSmall}`}
                  aria-label="Product type"
                  placeholder="Product type"
                  maxLength={60}
                  value={row.productType}
                  disabled={disabled}
                  onChange={(e) => update(row.key, { productType: e.target.value })}
                />
                <input
                  className={`${styles.input} ${styles.inputSmall}`}
                  aria-label="Brand"
                  placeholder="Brand"
                  maxLength={60}
                  value={row.brand ?? ""}
                  disabled={disabled}
                  onChange={(e) => update(row.key, { brand: e.target.value || null })}
                />
              </div>
              <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <CategoryChip category={row.category} label={label(row.category)} />
                {row.confidence !== null ? (
                  <span className={styles.conf}>AI confidence {Math.round(row.confidence * 100)}%</span>
                ) : (
                  <span className={styles.conf}>Added by operator</span>
                )}
                {low && <span className={styles.lowTag}>⚠ Low confidence — please check</span>}
              </div>
            </li>
          );
        })}
      </ul>
      <div style={{ marginTop: 12 }}>
        <Button variant="secondary" onClick={() => onChange([...rows, emptyRow()])} disabled={disabled} data-testid="item-add">
          + Add item
        </Button>
      </div>
    </div>
  );
}
