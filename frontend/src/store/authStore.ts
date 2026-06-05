import { create } from "zustand";
import { persist } from "zustand/middleware";
import Cookies from "js-cookie";
import type { User } from "@/lib/types";
import api from "@/lib/api";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, mfaCode?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password, mfaCode) => {
        set({ isLoading: true });
        try {
          const response = await api.login(email, password, mfaCode);
          Cookies.set("access_token", response.access_token, {
            expires: response.expires_in / 86400,
            secure: process.env.NODE_ENV === "production",
            sameSite: "strict",
          });
          Cookies.set("refresh_token", response.refresh_token, {
            expires: 7,
            secure: process.env.NODE_ENV === "production",
            sameSite: "strict",
          });
          set({ user: response.user, isAuthenticated: true, isLoading: false });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: () => {
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        set({ user: null, isAuthenticated: false });
        window.location.href = "/login";
      },

      refreshUser: async () => {
        try {
          const user = await api.getMe();
          set({ user, isAuthenticated: true });
        } catch {
          get().logout();
        }
      },
    }),
    {
      name: "iccbpo-auth",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
