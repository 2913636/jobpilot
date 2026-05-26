import { create } from "zustand";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

interface AppState {
  user: User | null;
  token: string | null;
  collapsed: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  toggleCollapsed: () => void;
  logout: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  token: typeof window !== "undefined" ? localStorage.getItem("token") : null,
  collapsed: false,
  setUser: (user) => set({ user }),
  setToken: (token) => {
    if (token) {
      localStorage.setItem("token", token);
    } else {
      localStorage.removeItem("token");
    }
    set({ token });
  },
  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
  logout: () => {
    localStorage.removeItem("token");
    set({ user: null, token: null });
  },
}));
