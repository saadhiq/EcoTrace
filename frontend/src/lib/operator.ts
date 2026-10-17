import type { User } from "firebase/auth";

import { ApiError, apiFetch } from "@/lib/api";

/** Warehouse operator API + waste taxonomy. */

export type Option = { id: string; label: string };
export type Taxonomy = { categories: Option[]; hazardFlags: Option[]; segregationQualities: string[] };
export type Segregation = "good" | "mixed" | "poor";

export type WasteItem = {
  name: string;
  category: string;
  material: string;
  productType: string;
  brand: string | null;
  quantity: number;
  recyclable: boolean;
};
export type AiItem = WasteItem & { confidence: number };
export type AiResult = { items: AiItem[]; segregationQuality: Segregation; hazardFlags: string[]; notes: string };
export type TokenUsage = { prompt: number; output: number; thoughts: number; total: number };

export type WasteRecord = {
  bagCode: string;
  status: "draft" | "confirmed";
  photoPaths: string[];
  aiResult: AiResult | null;
  aiError: string | null;
  model: string | null;
  latencyMs: number | null;
  tokenUsage: TokenUsage | null;
  finalItems: WasteItem[];
  segregationQuality: Segregation | null;
  hazardFlags: string[];
  edited: boolean;
  editCount: number;
  source: "ai" | "ai_edited" | "manual" | null;
};

export type QueueItem = {
  code: string;
  pickupId: string | null;
  zone: string | null;
  pickupDate: string | null;
  arrivedAt: string | null;
  hasDraft: boolean;
};

export type BagView = {
  code: string;
  status: string;
  pickupId: string | null;
  zone: string | null;
  pickupDate: string | null;
  bagsInPickup: number;
  processedInPickup: number;
  record: WasteRecord | null;
};

export type AnalyzeResult = {
  result: AiResult;
  model: string;
  latencyMs: number;
  tokenUsage: TokenUsage;
  photoCount: number;
};

export type FinalItem = WasteItem & { aiIndex: number | null };
export type ConfirmResult = { record: WasteRecord; pickupProcessed: boolean };

let taxonomyPromise: Promise<Taxonomy> | null = null;

export function fetchTaxonomy(): Promise<Taxonomy> {
  taxonomyPromise ??= apiFetch<Taxonomy>("/taxonomy").catch((err: unknown) => {
    taxonomyPromise = null;
    throw err;
  });
  return taxonomyPromise;
}

const bagPath = (code: string) => `/operator/bags/${encodeURIComponent(code)}`;

export const operatorApi = {
  queue: async (user: User) => apiFetch<QueueItem[]>("/operator/queue", { token: await user.getIdToken() }),
  bag: async (user: User, code: string) => apiFetch<BagView>(bagPath(code), { token: await user.getIdToken() }),
  analyze: async (user: User, code: string, photos: Blob[]) => {
    const form = new FormData();
    photos.forEach((photo, i) => form.append("photos", photo, `photo-${i + 1}.jpg`));
    return apiFetch<AnalyzeResult>(`${bagPath(code)}/analyze`, {
      method: "POST",
      token: await user.getIdToken(),
      form,
    });
  },
  confirm: async (
    user: User,
    code: string,
    body: { finalItems: FinalItem[]; segregationQuality: Segregation; hazardFlags: string[] },
  ) =>
    apiFetch<ConfirmResult>(`${bagPath(code)}/confirm`, {
      method: "POST",
      token: await user.getIdToken(),
      body,
    }),
};

const MESSAGES: Record<string, string> = {
  ai_unavailable: "Gemini didn't respond in time. Enter the items manually below.",
  ai_invalid_output: "Gemini returned an unexpected answer. Enter the items manually below.",
  photo_upload_failed: "Couldn't store the photo. Try again, or enter the items manually.",
  photo_count: "Add 1 to 3 photos.",
  photo_too_large: "That photo is too large (max 4 MB after resizing).",
  unsupported_photo_type: "Use a JPEG, PNG or WebP photo.",
  rate_limited: "Too many analyses in a minute. Wait a moment and try again.",
  not_at_warehouse: "This bag isn't waiting at the warehouse.",
  already_processed: "This bag has already been processed.",
  unknown_code: "Unknown bag code.",
  no_items: "Add at least one item.",
  invalid_ai_index: "The item list changed. Reload the bag and try again.",
};

export function operatorErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return "No connection. Check your network and try again.";
    if (MESSAGES[err.detail]) return MESSAGES[err.detail];
    if (err.status === 422) return "Please check the items and try again.";
  }
  return "Something went wrong. Please try again.";
}

/** True when the analyze call failed in a way where manual entry is the way forward. */
export function isAiFailure(err: unknown): boolean {
  return err instanceof ApiError && (err.detail === "ai_unavailable" || err.detail === "ai_invalid_output" || err.status === 0 || err.status >= 500);
}

export const SAMPLE_PHOTOS = [
  { file: "bag-recyclables.jpg", label: "Bottles & cans" },
  { file: "packaging.jpg", label: "Packaging" },
  { file: "e-waste.jpg", label: "Old phones" },
  { file: "mixed-waste.jpg", label: "Mixed waste" },
];

export const LOW_CONFIDENCE = 0.6;
