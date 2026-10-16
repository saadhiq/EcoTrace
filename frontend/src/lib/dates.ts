// Pickup dates are calendar days in Colombo (UTC+5:30, no DST), matching the API.
const COLOMBO_OFFSET_MS = (5 * 60 + 30) * 60 * 1000;
export const MAX_DAYS_AHEAD = 14;

/** YYYY-MM-DD for today in Colombo, shifted by `days`. */
export function colomboDate(days = 0, now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + COLOMBO_OFFSET_MS + days * 86_400_000);
  return shifted.toISOString().slice(0, 10);
}

export function pickupWindow(now: Date = new Date()): { min: string; max: string } {
  return { min: colomboDate(1, now), max: colomboDate(MAX_DAYS_AHEAD, now) };
}

/** "Tue, 21 Oct" for a YYYY-MM-DD string (timezone-independent). */
export function formatDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

export function formatDateTime(value: Date | null): string {
  if (!value) return "";
  return value.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Colombo",
  });
}
