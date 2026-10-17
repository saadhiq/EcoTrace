"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import styles from "@/components/resident/insights/insights.module.css";
import Card from "@/components/ui/Card";
import CategoryChip from "@/components/ui/CategoryChip";
import FullPageSpinner from "@/components/ui/FullPageSpinner";
import Logo from "@/components/ui/Logo";

const LKR = new Intl.NumberFormat("en-LK", { style: "currency", currency: "LKR", maximumFractionDigits: 0 });

/** Landing page for the FICTIONAL demo partners' products (no real shop behind it). */
function Product() {
  const q = useSearchParams();
  const name = q.get("name") ?? "Product";
  const partner = q.get("partnerName") ?? q.get("partner") ?? "Demo partner";
  const category = q.get("category") ?? "other";
  const price = Number(q.get("price") ?? "0");
  return (
    <main style={{ maxWidth: 560, margin: "0 auto", padding: "32px 16px", display: "flex", flexDirection: "column", gap: 16 }}>
      <Logo />
      <Card data-testid="demo-store">
        <p className={styles.small}>{partner} · demo partner store</p>
        <h1 style={{ fontSize: "1.5rem", margin: "8px 0" }}>{name}</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <CategoryChip category={category} label={category.replace("_", " & ")} />
          <span className={styles.small}>SKU {q.get("sku")}</span>
        </div>
        {q.get("benefit") && <p style={{ marginTop: 12 }}>♻ {q.get("benefit")}</p>}
        {price > 0 && <p style={{ marginTop: 8, fontSize: "1.25rem", fontWeight: 700 }}>{LKR.format(price)}</p>}
        <p className={styles.explain} style={{ marginTop: 16 }}>
          {partner} is a fictional partner created for the EcoTrace hackathon demo. In production this button would open
          the partner&apos;s own shop. Your click was counted anonymously (partner, product and day only).
        </p>
      </Card>
    </main>
  );
}

export default function DemoStorePage() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Product />
    </Suspense>
  );
}
