"use client";

import { create } from "zustand";

import type { AuthUser } from "@/types/auth";

type AuthStatus = "idle" | "loading" | "authenticated" | "unauthenticated";

type AuthState = {
  user: AuthUser | null;
  status: AuthStatus;
  setLoading: () => void;
  setUser: (user: AuthUser) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "idle",
  setLoading: () => set({ status: "loading" }),
  setUser: (user) => set({ user, status: "authenticated" }),
  clear: () => set({ user: null, status: "unauthenticated" }),
}));
