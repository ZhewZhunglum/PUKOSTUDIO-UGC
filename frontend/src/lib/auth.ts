"use client";

import { create } from "zustand";
import api from "./api";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, teamName?: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const res = await api.post("/auth/login", { email, password });
      localStorage.setItem("access_token", res.data.access_token);
      localStorage.setItem("refresh_token", res.data.refresh_token);
      set({ isAuthenticated: true });

      const userRes = await api.get("/auth/me");
      set({ user: userRes.data, isLoading: false });
    } catch (error) {
      set({ isLoading: false, isAuthenticated: false, user: null });
      throw error;
    }
  },

  register: async (email: string, password: string, name: string, teamName?: string) => {
    set({ isLoading: true });
    try {
      const res = await api.post("/auth/register", {
        email,
        password,
        name,
        team_name: teamName,
      });
      localStorage.setItem("access_token", res.data.access_token);
      localStorage.setItem("refresh_token", res.data.refresh_token);
      set({ isAuthenticated: true });

      const userRes = await api.get("/auth/me");
      set({ user: userRes.data, isLoading: false });
    } catch (error) {
      set({ isLoading: false, isAuthenticated: false, user: null });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, isAuthenticated: false, isLoading: false });
    window.location.href = "/login";
  },

  fetchUser: async () => {
    try {
      set({ isLoading: true });
      const res = await api.get("/auth/me");
      set({ user: res.data, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
