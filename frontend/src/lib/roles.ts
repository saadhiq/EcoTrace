export const ROLES = ["resident", "collector", "operator", "admin"] as const;
export type Role = (typeof ROLES)[number];

export const ROLE_LABELS: Record<Role, string> = {
  resident: "Resident",
  collector: "Collector",
  operator: "Warehouse operator",
  admin: "Admin",
};

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  resident: "Schedule pickups and see your household's waste history.",
  collector: "See assigned pickups and scan bag QR codes.",
  operator: "Photograph bag contents for Gemini classification.",
  admin: "Manage users, zones and collectors; view stats.",
};

export function dashboardPath(role: Role): string {
  return `/${role}`;
}

export type Profile = {
  uid: string;
  name: string;
  email: string | null;
  role: Role;
  createdAt: string | null;
};
