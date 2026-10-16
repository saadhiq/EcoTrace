import type { User } from "firebase/auth";

import { ApiError, apiFetch } from "@/lib/api";
import type { PickupStatus, TimeSlot } from "@/lib/types";

/** Collector-flow API. Bag codes are only ever returned once scanned. */

export type CollectorPickup = {
  id: string;
  date: string;
  timeSlot: TimeSlot;
  status: PickupStatus;
  zone: string;
  householdName: string;
  addressLine: string;
  phone: string;
  notes: string;
  bagCount: number;
  scannedCount: number;
  mine: boolean;
  missedReason: string | null;
  missingBagsReason: string | null;
};

export type BagSlot = {
  slot: number;
  status: string; // bag status, or "released"
  code: string | null;
};

export type CollectorPickupDetail = CollectorPickup & { slots: BagSlot[] };

export type DayView = {
  date: string;
  zones: string[];
  available: CollectorPickup[];
  mine: CollectorPickup[];
};

export type ScanResult = {
  code: string;
  slot: number;
  alreadyScanned: boolean;
  pickup: CollectorPickupDetail;
};

export type HandoverPickup = {
  pickupId: string;
  date: string;
  householdName: string;
  bags: BagSlot[];
};

export type HandoverScanResult = {
  code: string;
  alreadyScanned: boolean;
  pickupId: string;
  pickupDelivered: boolean;
};

async function call<T>(user: User, path: string, body?: unknown): Promise<T> {
  const token = await user.getIdToken();
  return body === undefined
    ? apiFetch<T>(path, { token })
    : apiFetch<T>(path, { method: "POST", token, body });
}

const p = (id: string) => `/collector/pickups/${encodeURIComponent(id)}`;

export const collectorApi = {
  day: (user: User, date: string) => call<DayView>(user, `/collector/pickups?date=${date}`),
  pickup: (user: User, id: string) => call<CollectorPickupDetail>(user, p(id)),
  accept: (user: User, id: string) => call<CollectorPickupDetail>(user, `${p(id)}/accept`, {}),
  scan: (user: User, id: string, code: string) => call<ScanResult>(user, `${p(id)}/scan`, { code }),
  simulateScan: (user: User, id: string, slot: number) =>
    call<ScanResult>(user, `${p(id)}/simulate-scan`, { slot }),
  complete: (user: User, id: string, missingReason?: string) =>
    call<CollectorPickupDetail>(user, `${p(id)}/complete`, missingReason ? { missingReason } : {}),
  missed: (user: User, id: string, reason: string) =>
    call<CollectorPickupDetail>(user, `${p(id)}/missed`, { reason }),
  handover: (user: User) => call<HandoverPickup[]>(user, "/collector/handover"),
  handoverScan: (user: User, code: string) =>
    call<HandoverScanResult>(user, "/collector/handover/scan", { code }),
};

const MESSAGES: Record<string, string> = {
  invalid_code: "That code isn't valid — check for typos.",
  unknown_code: "Unknown code.",
  wrong_pickup: "This bag belongs to another pickup.",
  pickup_not_active: "This pickup is no longer active.",
  pickup_not_found: "Pickup not found.",
  pickup_not_available: "Another collector already took this pickup.",
  outside_your_zones: "This pickup is outside your zones.",
  nothing_scanned: "Scan at least one bag, or mark the pickup as missed.",
  missing_reason_required: "Tell us why some bags are missing.",
  reason_required: "Please add a reason.",
  reason_too_long: "Please keep the reason under 280 characters.",
  bags_already_scanned: "Bags were already scanned — use “Complete with missing bags” instead.",
  not_in_your_van: "This bag isn't in your van.",
  invalid_transition: "That action isn't allowed for this pickup any more.",
  demo_only: "Simulated scans are only available on demo accounts.",
};

export function collectorErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return "No connection. Check your signal and try again.";
    if (MESSAGES[err.detail]) return MESSAGES[err.detail];
  }
  return "Something went wrong. Please try again.";
}

/** Google Maps directions link (plain URL, no API key). */
export function directionsUrl(address: string, zoneName: string): string {
  const destination = `${address}, ${zoneName}, Sri Lanka`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
}
