import type { User } from "firebase/auth";

import { ApiError, apiFetch } from "@/lib/api";
import type { Household, TimeSlot, Zone } from "@/lib/types";

/** Resident-flow API calls. All writes go through the backend. */

let zonesPromise: Promise<Zone[]> | null = null;

export function fetchZones(): Promise<Zone[]> {
  zonesPromise ??= apiFetch<Zone[]>("/zones").catch((err: unknown) => {
    zonesPromise = null;
    throw err;
  });
  return zonesPromise;
}

export async function fetchMyHousehold(user: User): Promise<Household | null> {
  try {
    return await apiFetch<Household>("/households/me", { token: await user.getIdToken() });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export type HouseholdInput = {
  name: string;
  phone: string;
  addressLine: string;
  zone: string;
};

export async function createHousehold(user: User, input: HouseholdInput): Promise<Household> {
  const res = await apiFetch<{ household: Household }>("/households", {
    method: "POST",
    token: await user.getIdToken(),
    body: input,
  });
  return res.household;
}

export async function requestMoreBags(user: User): Promise<number> {
  const bags = await apiFetch<unknown[]>("/bags/request-more", {
    method: "POST",
    token: await user.getIdToken(),
  });
  return bags.length;
}

export type PickupInput = {
  date: string;
  timeSlot: TimeSlot;
  bagCodes: string[];
  notes: string;
};

export async function schedulePickup(user: User, input: PickupInput): Promise<void> {
  await apiFetch("/pickups", { method: "POST", token: await user.getIdToken(), body: input });
}

export async function cancelPickup(user: User, pickupId: string): Promise<void> {
  await apiFetch(`/pickups/${encodeURIComponent(pickupId)}/cancel`, {
    method: "POST",
    token: await user.getIdToken(),
  });
}

const API_MESSAGES: Record<string, string> = {
  household_exists: "You already have a household.",
  invalid_zone: "Please choose a zone from the list.",
  no_household: "Set up your household first.",
  bag_limit_reached: "You already have 20 unused bags — use some before requesting more.",
  date_out_of_range: "Pick a date from tomorrow up to 14 days ahead.",
  invalid_bag_count: "Choose between 1 and 5 bags.",
  duplicate_bags: "Each bag can only be added once.",
  bag_not_owned: "One of those bags isn't yours.",
  bag_not_available: "One of those bags is already scheduled. Refresh and try again.",
  pickup_exists_for_date: "You already have a pickup on that date.",
  not_cancellable: "This pickup can no longer be cancelled.",
  pickup_not_found: "That pickup no longer exists.",
};

export function residentErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return "Can't reach the EcoTrace API. Check your connection.";
    if (API_MESSAGES[err.detail]) return API_MESSAGES[err.detail];
    if (err.status === 422) return "Please check the form and try again.";
  }
  return "Something went wrong. Please try again.";
}
