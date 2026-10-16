import { FirebaseError } from "firebase/app";

import { ApiError } from "@/lib/api";

const FIREBASE_MESSAGES: Record<string, string> = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/invalid-email": "Please enter a valid email address.",
  "auth/user-disabled": "This account has been disabled.",
  "auth/email-already-in-use": "An account with this email already exists. Try signing in.",
  "auth/weak-password": "Password must be at least 6 characters.",
  "auth/too-many-requests": "Too many attempts. Please wait a moment and try again.",
  "auth/network-request-failed": "Network error. Check your connection and try again.",
};

export function authErrorMessage(err: unknown): string {
  if (err instanceof FirebaseError) {
    return FIREBASE_MESSAGES[err.code] ?? "Something went wrong. Please try again.";
  }
  if (err instanceof ApiError) {
    if (err.status === 429) return "Too many demo sign-ins from your network. Try again in a minute.";
    if (err.status === 0) return "Can't reach the EcoTrace API. Check your connection.";
  }
  return "Something went wrong. Please try again.";
}
