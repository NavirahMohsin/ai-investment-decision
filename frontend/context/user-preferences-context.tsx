"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Theme = "dark" | "light" | "system";
export type DateFormat = "DD/MM/YYYY" | "MM/DD/YYYY" | "YYYY-MM-DD";

export interface UserPreferences {
  theme: Theme;
  dateFormat: DateFormat;
  currency: "INR" | "USD";
  defaultWatchlistId?: number;
  defaultDashboardLayout: "compact" | "standard" | "detailed";
  autoRefreshQuotes: boolean;
  autoRefreshInterval: number; // in minutes
  showMarketStatus: boolean;
  showSectorPerformance: boolean;
  showRecentNews: boolean;
  showWatchlistPerformance: boolean;
  enableNotifications: boolean;
  notificationSound: boolean;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  theme: "dark",
  dateFormat: "DD/MM/YYYY",
  currency: "INR",
  defaultDashboardLayout: "standard",
  autoRefreshQuotes: true,
  autoRefreshInterval: 5,
  showMarketStatus: true,
  showSectorPerformance: true,
  showRecentNews: true,
  showWatchlistPerformance: true,
  enableNotifications: false,
  notificationSound: false,
};

interface UserPreferencesContextValue {
  preferences: UserPreferences;
  loading: boolean;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
  resetPreferences: () => void;
}

const UserPreferencesContext = createContext<UserPreferencesContextValue | null>(
  null
);

export function UserPreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);

  // Load preferences from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("userPreferences");
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<UserPreferences>;
        setPreferences({
          ...DEFAULT_PREFERENCES,
          ...parsed,
        });
      }
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, []);

  // Apply theme to document
  useEffect(() => {
    const theme = preferences.theme;
    if (theme === "system") {
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.classList.toggle("dark", isDark);
    } else {
      document.documentElement.classList.toggle("dark", theme === "dark");
    }
  }, [preferences.theme]);

  const updatePreferences = useCallback(
    (updates: Partial<UserPreferences>) => {
      setPreferences((prev) => {
        const updated = { ...prev, ...updates };
        try {
          localStorage.setItem("userPreferences", JSON.stringify(updated));
        } catch {
          // Silently fail if localStorage is unavailable
        }
        return updated;
      });
    },
    []
  );

  const resetPreferences = useCallback(() => {
    setPreferences(DEFAULT_PREFERENCES);
    try {
      localStorage.removeItem("userPreferences");
    } catch {
      // Silently fail
    }
  }, []);

  return (
    <UserPreferencesContext.Provider
      value={{
        preferences,
        loading,
        updatePreferences,
        resetPreferences,
      }}
    >
      {children}
    </UserPreferencesContext.Provider>
  );
}

export function useUserPreferences(): UserPreferencesContextValue {
  const ctx = useContext(UserPreferencesContext);
  if (!ctx) {
    throw new Error("useUserPreferences must be used inside UserPreferencesProvider");
  }
  return ctx;
}
