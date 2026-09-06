import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  phone_number?: string;
}

export interface AppState {
  // Authentication & Guest State
  accessToken: string | null;
  refreshToken: string | null;
  user: UserProfile | null;
  guestToken: string | null;
  isGuest: boolean;
  isHydrated: boolean;

  // Active Chat Session State
  activeSessionId: string;
  activeChatTitle: string;
  activeView: "chat" | "auth";
  isSidebarOpen: boolean;

  // Background / In-Flight Session Execution Tracking
  inFlightSessionIds: string[];

  // Phase 8 Itinerary Approval & Redraft State
  approvalStatus: Record<string, boolean>;

  // Actions
  setAuth: (tokens: { access: string; refresh: string }, user: UserProfile) => void;
  setTokens: (access: string, refresh?: string) => void;
  setGuestToken: (guestToken: string) => void;
  logout: () => void;
  setActiveSessionId: (sessionId: string) => void;
  setActiveChatTitle: (title: string) => void;
  setActiveView: (view: "chat" | "auth") => void;
  setSidebarOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  setApprovalStatus: (itineraryId: string, approved: boolean) => void;
  addInFlightSession: (sessionId: string) => void;
  removeInFlightSession: (sessionId: string) => void;
  rehydrateAuth: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Deterministic initial state (matches server and client during SSR)
      accessToken: null,
      refreshToken: null,
      user: null,
      guestToken: null,
      isGuest: true,
      isHydrated: false,

      // Chat Session State
      activeSessionId: "",
      activeChatTitle: "New Expedition Plan",
      activeView: "chat",
      isSidebarOpen: true,

      // Multi-chat background in-flight tracking
      inFlightSessionIds: [],

      // Approval status dictionary (itineraryId -> boolean)
      approvalStatus: {},

      // Actions
      setAuth: (tokens, user) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("humsafar_access_token", tokens.access);
          localStorage.setItem("humsafar_refresh_token", tokens.refresh);
          localStorage.setItem("humsafar_user", JSON.stringify(user));
        }
        set({
          accessToken: tokens.access,
          refreshToken: tokens.refresh,
          user,
          isGuest: false,
          activeView: "chat",
        });
      },

      setTokens: (access, refresh) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("humsafar_access_token", access);
          if (refresh) {
            localStorage.setItem("humsafar_refresh_token", refresh);
          }
        }
        set((state) => ({
          accessToken: access,
          refreshToken: refresh || state.refreshToken,
        }));
      },

      setGuestToken: (guestToken) => {
        if (typeof window !== "undefined") {
          sessionStorage.setItem("humsafar_guest_token", guestToken);
          localStorage.setItem("humsafar_guest_token", guestToken);
        }
        set({
          guestToken,
          isGuest: true,
        });
      },

      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("humsafar_access_token");
          localStorage.removeItem("humsafar_refresh_token");
          localStorage.removeItem("humsafar_user");
          sessionStorage.removeItem("humsafar_guest_token");
        }
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          guestToken: null,
          isGuest: true,
          activeSessionId: "",
          activeChatTitle: "New Expedition Plan",
          activeView: "chat",
          inFlightSessionIds: [],
          approvalStatus: {},
        });
      },

      setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
      setActiveChatTitle: (activeChatTitle) => set({ activeChatTitle }),
      setActiveView: (activeView) => set({ activeView }),
      setSidebarOpen: (updater) =>
        set((state) => ({
          isSidebarOpen:
            typeof updater === "function" ? updater(state.isSidebarOpen) : updater,
        })),

      setApprovalStatus: (itineraryId, approved) =>
        set((state) => ({
          approvalStatus: {
            ...state.approvalStatus,
            [itineraryId]: approved,
          },
        })),

      addInFlightSession: (sessionId) =>
        set((state) => ({
          inFlightSessionIds: state.inFlightSessionIds.includes(sessionId)
            ? state.inFlightSessionIds
            : [...state.inFlightSessionIds, sessionId],
        })),

      removeInFlightSession: (sessionId) =>
        set((state) => ({
          inFlightSessionIds: state.inFlightSessionIds.filter((id) => id !== sessionId),
        })),

      rehydrateAuth: () => {
        if (typeof window === "undefined") return;
        useAppStore.persist.rehydrate();
        const cur = get();
        if (!cur.user) {
          try {
            const access = localStorage.getItem("humsafar_access_token");
            const refresh = localStorage.getItem("humsafar_refresh_token");
            const userRaw = localStorage.getItem("humsafar_user");
            const user = userRaw ? JSON.parse(userRaw) : null;
            const guest =
              sessionStorage.getItem("humsafar_guest_token") ||
              localStorage.getItem("humsafar_guest_token");
            if (access && refresh && user) {
              set({
                accessToken: access,
                refreshToken: refresh,
                user,
                isGuest: false,
              });
            } else if (guest) {
              set({ guestToken: guest, isGuest: true });
            }
          } catch {
            // ignore
          }
        }
        set({ isHydrated: true });
      },
    }),
    {
      name: "humsafar_app_store",
      storage: createJSONStorage(() => (typeof window !== "undefined" ? localStorage : {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
      })),
      skipHydration: true,
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        guestToken: state.guestToken,
        isGuest: state.isGuest,
        activeSessionId: state.activeSessionId,
        activeChatTitle: state.activeChatTitle,
        approvalStatus: state.approvalStatus,
      }),
    }
  )
);
