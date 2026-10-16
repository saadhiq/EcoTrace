"use client";

import {
  collection,
  onSnapshot,
  orderBy,
  query,
  Timestamp,
  where,
  type DocumentData,
} from "firebase/firestore";
import { useEffect, useState } from "react";

import { firestoreDb } from "@/lib/firebase";
import type { Bag, Pickup, StatusEvent } from "@/lib/types";

export type LiveState<T> =
  | { status: "loading" }
  | { status: "ready"; items: T[] }
  | { status: "error"; message: string };

function toDate(value: unknown): Date | null {
  return value instanceof Timestamp ? value.toDate() : null;
}

function toHistory(value: unknown): StatusEvent[] {
  if (!Array.isArray(value)) return [];
  return value.map((e: DocumentData) => ({ status: e.status, at: toDate(e.at), by: e.by }));
}

function toPickup(id: string, d: DocumentData): Pickup {
  return {
    id,
    householdId: d.householdId,
    residentUid: d.residentUid,
    zone: d.zone,
    date: d.date,
    timeSlot: d.timeSlot,
    bagCodes: d.bagCodes ?? [],
    notes: d.notes ?? "",
    status: d.status,
    collectorUid: d.collectorUid ?? null,
    statusHistory: toHistory(d.statusHistory),
    createdAt: toDate(d.createdAt),
  };
}

function toBag(code: string, d: DocumentData): Bag {
  return {
    code,
    householdId: d.householdId,
    ownerUid: d.ownerUid,
    status: d.status,
    pickupId: d.pickupId ?? null,
    issuedAt: toDate(d.issuedAt),
    statusHistory: toHistory(d.statusHistory),
  };
}

type Source = "pickups" | "bags";

/**
 * Live Firestore listener scoped to the signed-in resident. The query filters
 * on ownerUid/residentUid so it satisfies the security rules.
 */
function useLive<T>(source: Source, uid: string, map: (id: string, d: DocumentData) => T): LiveState<T> {
  const [state, setState] = useState<LiveState<T>>({ status: "loading" });

  useEffect(() => {
    const db = firestoreDb();
    const q =
      source === "pickups"
        ? query(collection(db, "pickups"), where("residentUid", "==", uid), orderBy("date", "desc"))
        : query(collection(db, "bags"), where("ownerUid", "==", uid), orderBy("issuedAt", "asc"));
    return onSnapshot(
      q,
      (snap) => setState({ status: "ready", items: snap.docs.map((doc) => map(doc.id, doc.data())) }),
      () => setState({ status: "error", message: "Live updates are unavailable right now." }),
    );
    // `map` is a module-level function; re-subscribe only when the query changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, uid]);

  return state;
}

export function useMyPickups(uid: string): LiveState<Pickup> {
  return useLive("pickups", uid, toPickup);
}

export function useMyBags(uid: string): LiveState<Bag> {
  return useLive("bags", uid, toBag);
}
