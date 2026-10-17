"use client";

import type { User } from "firebase/auth";
import { collection, doc, limit, onSnapshot, orderBy, query, Timestamp } from "firebase/firestore";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { firestoreDb } from "@/lib/firebase";
import type { WasteItem } from "@/lib/operator";

/**
 * Fixed category display order. It matches the validated categorical palette's
 * slot order (adjacent colors are separable incl. colour-blind), and colour
 * follows the category, never its rank. Keep every row, even at zero.
 */
export const CATEGORY_ORDER = [
  "plastic",
  "paper_cardboard",
  "glass",
  "metal",
  "textile",
  "organic",
  "e_waste",
  "hazardous",
  "other",
] as const;

export const SCORE_EXPLANATION =
  "50% sorting quality + 30% recyclable share + 20% safe hazard disposal, across all your processed bags.";

export type CategoryStat = { items: number; quantity: number };
export type PickupPoint = {
  pickupId: string;
  date: string | null;
  bags: number;
  quantity: number;
  recyclableShare: number | null;
  ecoScore: number | null;
};
export type HouseholdStats = {
  categories: Record<string, CategoryStat>;
  totalItems: number;
  totalQuantity: number;
  recyclableQuantity: number;
  recyclableShare: number | null;
  bagsProcessed: number;
  pickupsProcessed: number;
  segregation: Record<string, number>;
  hazards: Record<string, number>;
  hazardBags: number;
  safeHazardBags: number;
  ecoScore: number | null;
  scoreParts: { sorting: number; recycling: number; hazards: number } | null;
  points: number;
  byPickup: PickupPoint[];
  statsHash: string;
  lastUpdated: Date | null;
};
export type LedgerEntry = { id: string; bagCode: string; reason: string; points: number; at: Date | null };

export const LEDGER_LABELS: Record<string, string> = {
  bag_processed: "Bag processed",
  good_segregation: "Well-sorted bag",
  hazards_separated: "Hazards packed separately",
};

type Live<T> = { status: "loading" } | { status: "ready"; value: T } | { status: "error" };

/** households/{uid}/stats/summary, live (null = no processed bags yet). */
export function useHouseholdStats(uid: string): Live<HouseholdStats | null> {
  const [state, setState] = useState<Live<HouseholdStats | null>>({ status: "loading" });
  useEffect(
    () =>
      onSnapshot(
        doc(firestoreDb(), "households", uid, "stats", "summary"),
        (snap) => {
          if (!snap.exists()) return setState({ status: "ready", value: null });
          const d = snap.data();
          setState({
            status: "ready",
            value: { ...(d as HouseholdStats), lastUpdated: d.lastUpdated instanceof Timestamp ? d.lastUpdated.toDate() : null },
          });
        },
        () => setState({ status: "error" }),
      ),
    [uid],
  );
  return state;
}

/** Most recent points ledger entries, live. */
export function useRecentPoints(uid: string, count = 5): Live<LedgerEntry[]> {
  const [state, setState] = useState<Live<LedgerEntry[]>>({ status: "loading" });
  useEffect(
    () =>
      onSnapshot(
        query(collection(firestoreDb(), "households", uid, "pointsLedger"), orderBy("at", "desc"), limit(count)),
        (snap) =>
          setState({
            status: "ready",
            value: snap.docs.map((d) => {
              const data = d.data();
              return {
                id: d.id,
                bagCode: data.bagCode,
                reason: data.reason,
                points: data.points,
                at: data.at instanceof Timestamp ? data.at.toDate() : null,
              };
            }),
          }),
        () => setState({ status: "error" }),
      ),
    [uid, count],
  );
  return state;
}

// --- API ---

export type Lang = "en" | "si" | "ta";
export const LANG_LABELS: Record<Lang, string> = { en: "English", si: "සිංහල", ta: "தமிழ்" };
export type Tip = { title: string; body: string; category: string };
export type TipsResponse = {
  lang: Lang;
  tips: Tip[];
  source: "gemini" | "cache" | "fallback" | "starter";
  model: string | null;
  generatedAt: string | null;
  latencyMs: number | null;
};

export type ConsentEntry = { value: boolean; at: string; by: string; textVersion: string };
export type ConsentView = { dataSharing: boolean; updatedAt: string | null; textVersion: string; history: ConsentEntry[] };

export type BagDetail = {
  code: string;
  slot: number;
  status: string;
  items: WasteItem[];
  segregationQuality: string | null;
  hazardFlags: string[];
};
export type PickupDetails = { pickupId: string; date: string; status: string; bags: BagDetail[] };

export const insightsApi = {
  tips: async (user: User, lang: Lang) =>
    apiFetch<TipsResponse>(`/residents/me/tips?lang=${lang}`, { method: "POST", token: await user.getIdToken() }),
  consent: async (user: User) => apiFetch<ConsentView>("/households/me/consent", { token: await user.getIdToken() }),
  setConsent: async (user: User, dataSharing: boolean) =>
    apiFetch<ConsentView>("/households/me/consent", {
      method: "PUT",
      token: await user.getIdToken(),
      body: { dataSharing },
    }),
  pickupDetails: async (user: User, pickupId: string) =>
    apiFetch<PickupDetails>(`/residents/me/pickups/${encodeURIComponent(pickupId)}/details`, {
      token: await user.getIdToken(),
    }),
};

// --- sustainable swaps ---

export type SwapPick = {
  sku: string;
  partnerId: string;
  partnerName: string;
  name: string;
  category: string;
  ecoBenefit: string;
  price: number;
  url: string;
  reason: string;
};
export type SwapsResponse = {
  picks: SwapPick[];
  source: "gemini" | "cache" | "fallback" | "none";
  model: string | null;
  latencyMs: number | null;
};

export const swapsApi = {
  list: async (user: User) => apiFetch<SwapsResponse>("/residents/me/swaps", { token: await user.getIdToken() }),
  click: async (user: User, sku: string) =>
    apiFetch<{ url: string }>(`/residents/me/swaps/${encodeURIComponent(sku)}/click`, {
      method: "POST",
      token: await user.getIdToken(),
    }),
};
