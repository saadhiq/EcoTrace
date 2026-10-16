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
import type { Bag, Pickup, RouteStop, StatusEvent } from "@/lib/types";

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
    missedReason: d.missedReason ?? null,
    missingBagsReason: d.missingBagsReason ?? null,
  };
}

function toRouteStop(pickupId: string, d: DocumentData): RouteStop {
  return {
    pickupId,
    collectorUid: d.collectorUid,
    date: d.date,
    timeSlot: d.timeSlot,
    status: d.status,
    zone: d.zone,
    householdName: d.householdName,
    addressLine: d.addressLine,
    bagCount: d.bagCount ?? 0,
    scannedCount: d.scannedCount ?? 0,
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

type Source = "pickups" | "bags" | "routes";

/**
 * Live Firestore listener scoped to the signed-in user. Every query filters on
 * the caller's uid (ownerUid / residentUid / collectorUid) so the rules allow it.
 */
function useLive<T>(
  source: Source,
  uid: string,
  map: (id: string, d: DocumentData) => T,
  day?: string,
): LiveState<T> {
  const [state, setState] = useState<LiveState<T>>({ status: "loading" });

  useEffect(() => {
    const db = firestoreDb();
    const q =
      source === "pickups"
        ? query(collection(db, "pickups"), where("residentUid", "==", uid), orderBy("date", "desc"))
        : source === "bags"
          ? query(collection(db, "bags"), where("ownerUid", "==", uid), orderBy("issuedAt", "asc"))
          : query(collection(db, "routes"), where("collectorUid", "==", uid), where("date", "==", day ?? ""));
    return onSnapshot(
      q,
      (snap) => setState({ status: "ready", items: snap.docs.map((doc) => map(doc.id, doc.data())) }),
      () => setState({ status: "error", message: "Live updates are unavailable right now." }),
    );
    // `map` is a module-level function; re-subscribe only when the query changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, uid, day]);

  return state;
}

export function useMyPickups(uid: string): LiveState<Pickup> {
  return useLive("pickups", uid, toPickup);
}

export function useMyBags(uid: string): LiveState<Bag> {
  return useLive("bags", uid, toBag);
}

/** Collector: live code-free mirror of my assigned pickups on `day`. */
export function useMyRoute(uid: string, day: string): LiveState<RouteStop> {
  return useLive("routes", uid, toRouteStop, day);
}
