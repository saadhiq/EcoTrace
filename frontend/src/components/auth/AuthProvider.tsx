"use client";

import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithCustomToken,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  type User,
} from "firebase/auth";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { firebaseAuth } from "@/lib/firebase";
import type { Profile, Role } from "@/lib/roles";

export type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  | { status: "ready"; user: User; profile: Profile }
  | { status: "error"; message: string };

type AuthContextValue = {
  state: AuthState;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signInDemo: (role: Role) => Promise<void>;
  logout: () => Promise<void>;
  retry: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function registerAsResident(user: User, name?: string | null): Promise<void> {
  const token = await user.getIdToken();
  await apiFetch("/auth/register", { method: "POST", token, body: { name: name ?? null } });
  await user.getIdToken(true); // pick up the new role claim
}

async function fetchProfile(user: User): Promise<Profile> {
  return apiFetch<Profile>("/me", { token: await user.getIdToken() });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  // Ignore results from superseded loads (e.g. a fast logout/login).
  const generation = useRef(0);
  // While signUp() runs it owns profile loading, so the listener stays out.
  const signingUp = useRef(false);
  // Auto-register at most once per uid per session.
  const autoRegistered = useRef(new Set<string>());

  const loadProfile = useCallback(async (user: User) => {
    const gen = ++generation.current;
    setState({ status: "loading" });
    try {
      let profile: Profile;
      try {
        profile = await fetchProfile(user);
      } catch (err) {
        const notRegistered = err instanceof ApiError && err.detail === "not_registered";
        if (!notRegistered || autoRegistered.current.has(user.uid)) throw err;
        autoRegistered.current.add(user.uid);
        await registerAsResident(user, user.displayName);
        profile = await fetchProfile(user);
      }
      if (gen === generation.current) setState({ status: "ready", user, profile });
    } catch (err) {
      if (gen !== generation.current) return;
      const message =
        err instanceof ApiError && err.status === 0
          ? "Can't reach the EcoTrace API. Check your connection and try again."
          : "We couldn't load your account. Please try again.";
      setState({ status: "error", message });
    }
  }, []);

  useEffect(() => {
    return onAuthStateChanged(firebaseAuth(), (user) => {
      if (signingUp.current) return;
      if (!user) {
        generation.current++;
        setState({ status: "signedOut" });
        return;
      }
      void loadProfile(user);
    });
  }, [loadProfile]);

  const signIn = useCallback(async (email: string, password: string) => {
    await signInWithEmailAndPassword(firebaseAuth(), email, password);
  }, []);

  const signUp = useCallback(
    async (name: string, email: string, password: string) => {
      signingUp.current = true;
      try {
        const { user } = await createUserWithEmailAndPassword(firebaseAuth(), email, password);
        await updateProfile(user, { displayName: name });
        autoRegistered.current.add(user.uid);
        await registerAsResident(user, name);
        signingUp.current = false;
        await loadProfile(user);
      } finally {
        signingUp.current = false;
      }
    },
    [loadProfile],
  );

  const signInDemo = useCallback(async (role: Role) => {
    const { token } = await apiFetch<{ token: string }>(`/auth/demo/${role}`, {
      method: "POST",
    });
    await signInWithCustomToken(firebaseAuth(), token);
  }, []);

  const logout = useCallback(async () => {
    await signOut(firebaseAuth());
  }, []);

  const retry = useCallback(() => {
    const user = firebaseAuth().currentUser;
    if (user) void loadProfile(user);
    else setState({ status: "signedOut" });
  }, [loadProfile]);

  const value = useMemo(
    () => ({ state, signIn, signUp, signInDemo, logout, retry }),
    [state, signIn, signUp, signInDemo, logout, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
