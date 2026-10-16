export type Zone = { id: string; name: string };

export type Household = {
  id: string;
  ownerUid: string;
  name: string;
  phone: string;
  addressLine: string;
  zone: string;
  lat: number | null;
  lng: number | null;
  consent: { dataSharing: boolean; updatedAt: string | null };
  createdAt: string;
};

export const BAG_STATUSES = ["issued", "scheduled", "collected", "at_warehouse", "processed"] as const;
export type BagStatus = (typeof BAG_STATUSES)[number];

export const PICKUP_STEPS = ["requested", "assigned", "collected", "delivered", "processed"] as const;
export type PickupStatus = (typeof PICKUP_STEPS)[number] | "cancelled";

export const CANCELLABLE: PickupStatus[] = ["requested", "assigned"];

export type StatusEvent = { status: string; at: Date | null; by: string };

export type Bag = {
  code: string;
  householdId: string;
  ownerUid: string;
  status: BagStatus;
  pickupId: string | null;
  issuedAt: Date | null;
  statusHistory: StatusEvent[];
};

export type TimeSlot = "morning" | "afternoon";

export type Pickup = {
  id: string;
  householdId: string;
  residentUid: string;
  zone: string;
  date: string; // YYYY-MM-DD (Asia/Colombo)
  timeSlot: TimeSlot;
  bagCodes: string[];
  notes: string;
  status: PickupStatus;
  collectorUid: string | null;
  statusHistory: StatusEvent[];
  createdAt: Date | null;
};

export const STATUS_LABELS: Record<BagStatus | PickupStatus, string> = {
  issued: "Ready to use",
  scheduled: "Scheduled",
  requested: "Requested",
  assigned: "Assigned",
  collected: "Collected",
  at_warehouse: "At warehouse",
  delivered: "At warehouse",
  processed: "Processed",
  cancelled: "Cancelled",
};

export const SLOT_LABELS: Record<TimeSlot, string> = {
  morning: "Morning (8am–12pm)",
  afternoon: "Afternoon (1pm–5pm)",
};
