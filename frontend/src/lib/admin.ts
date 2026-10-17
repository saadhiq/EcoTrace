import type { User } from "firebase/auth";

import { ApiError, apiFetch } from "@/lib/api";
import type { Profile, Role } from "@/lib/roles";

/** Admin API (Cloud Run). Reads are cached ~60 s server-side. */

export type ZoneRow = {
  zone: string;
  households: number;
  bags: number;
  quantity: number;
  recyclableShare: number | null;
  topCategory: string | null;
  avgEcoScore: number | null;
};

export type Overview = {
  range: string;
  dateFrom: string;
  dateTo: string;
  includeSynthetic: boolean;
  syntheticHouseholds: number;
  pickupsToday: Record<string, number>;
  pickupsInRange: Record<string, number>;
  pickupsUpcoming: Record<string, number>;
  bagsProcessed: number;
  activeHouseholds: number;
  collectors: number;
  categories: Record<string, number>;
  totalQuantity: number;
  recyclableShare: number | null;
  zones: ZoneRow[];
  generatedAt: string;
};

export type AiQuality = {
  recordsConsidered: number;
  bagsAnalyzed: number;
  correctionRate: number | null;
  avgCorrectionsPerBag: number | null;
  avgLatencyMs: number | null;
  p95LatencyMs: number | null;
  failures: number;
  manualFallbacks: number;
  lowConfidenceShare: number | null;
  itemsAdded: number;
  itemsRemoved: number;
  itemsModified: number;
  estimatedEditRecords: number;
  models: Record<string, number>;
};

export type PickupRow = {
  id: string;
  date: string;
  timeSlot: string;
  status: string;
  zone: string;
  householdName: string;
  bagCount: number;
  collectorUid: string | null;
  collectorName: string | null;
  isDemo: boolean;
};

export type PickupPage = { items: PickupRow[]; page: number; pageSize: number; total: number };

export type TimelineEvent = { at: string; kind: "pickup" | "bag"; status: string; by: string; bagCode: string | null };

export type PickupDetail = {
  pickup: PickupRow;
  addressLine: string;
  notes: string;
  bags: { code: string; status: string; attached: boolean }[];
  timeline: TimelineEvent[];
  canReassign: boolean;
};

export type AdminUser = {
  uid: string;
  name: string;
  email: string | null;
  role: Role;
  createdAt: string | null;
  zones: string[];
  isSynthetic: boolean;
};

export type ProductStat = { sku: string; name: string; impressions: number; clicks: number };

export type PartnerRow = {
  id: string;
  name: string;
  active: boolean;
  isDemo: boolean;
  keyPrefix: string;
  catalogSize: number;
  impressions: number;
  clicks: number;
  ctr: number | null;
  topProducts: ProductStat[];
};

export type PartnerKey = { partner: PartnerRow; apiKey: string };

const ERRORS: Record<string, string> = {
  demo_disabled: "Disabled in the public demo.",
  not_reassignable: "This pickup can't be reassigned: a bag has already been scanned.",
  outside_collector_zones: "That collector doesn't cover this pickup's zone.",
  not_a_collector: "Choose a collector account.",
  already_assigned: "Already assigned to that collector.",
  email_exists: "An account with that email already exists.",
  partner_exists: "A partner with that name already exists.",
  invalid_zone: "Unknown zone.",
  network_error: "Can't reach the server. Check your connection.",
};

export function adminErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return ERRORS[err.detail] ?? `Something went wrong (${err.detail}).`;
  return "Something went wrong.";
}

export const isDemoDisabled = (err: unknown) => err instanceof ApiError && err.detail === "demo_disabled";

async function get<T>(user: User, path: string): Promise<T> {
  return apiFetch<T>(path, { token: await user.getIdToken() });
}

async function send<T>(user: User, path: string, body: unknown, method: "POST" | "PATCH" = "POST"): Promise<T> {
  return apiFetch<T>(path, { method, body, token: await user.getIdToken() });
}

export const fetchOverview = (user: User, range: "7d" | "30d", synthetic: boolean) =>
  get<Overview>(user, `/admin/overview?range=${range}&synthetic=${synthetic ? "include" : "exclude"}`);

export const fetchAiQuality = (user: User) => get<AiQuality>(user, "/admin/ai-quality");

export function fetchPickups(user: User, f: { date: string; zone: string; status: string; page: number }) {
  const q = new URLSearchParams({ date: f.date, page: String(f.page), pageSize: "20" });
  if (f.zone) q.set("zone", f.zone);
  if (f.status) q.set("status", f.status);
  return get<PickupPage>(user, `/admin/pickups?${q}`);
}

export const fetchPickup = (user: User, id: string) => get<PickupDetail>(user, `/admin/pickups/${encodeURIComponent(id)}`);

export const assignPickup = (user: User, id: string, collectorUid: string) =>
  send<PickupDetail>(user, `/admin/pickups/${encodeURIComponent(id)}/assign`, { collectorUid });

export const fetchUsers = (user: User, role?: Role) => get<AdminUser[]>(user, `/admin/users${role ? `?role=${role}` : ""}`);

export const createStaff = (user: User, body: { email: string; name: string; role: "collector" | "operator"; zones: string[] }) =>
  send<{ uid: string; setupLink: string }>(user, "/admin/staff", body);

export const setZones = (user: User, uid: string, zones: string[]) =>
  send<AdminUser>(user, `/admin/users/${encodeURIComponent(uid)}/zones`, { zones }, "PATCH");

export const fetchPartners = (user: User) => get<PartnerRow[]>(user, "/admin/partners");

export const createPartner = (user: User, name: string) => send<PartnerKey>(user, "/admin/partners", { name });

export const rotateKey = (user: User, id: string) =>
  send<PartnerKey>(user, `/admin/partners/${encodeURIComponent(id)}/rotate-key`, {});

export const fetchDemoKey = (user: User, id: string) =>
  get<{ partnerId: string; apiKey: string }>(user, `/admin/partners/${encodeURIComponent(id)}/demo-key`);

/** Server-to-server partner API, called here straight from the browser with the demo key. */
export const tryPartnerApi = (path: string, apiKey: string) => apiFetch<unknown>(path, { headers: { "X-API-Key": apiKey } });

export function maskKey(key: string): string {
  const dot = key.lastIndexOf(".");
  return dot > 0 ? `${key.slice(0, dot + 1)}${"•".repeat(12)}` : "•".repeat(16);
}

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export type AdminContext = { user: User; profile: Profile; isDemo: boolean; zoneName: (id: string | null) => string };
