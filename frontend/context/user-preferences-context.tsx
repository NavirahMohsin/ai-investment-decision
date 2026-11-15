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
  formatDate: (date: Date | string) => string;
  formatPrice: (price: number | string | null, symbol?: string) => string;
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

  // Apply theme to document and listen for system preference changes
  useEffect(() => {
    const applyTheme = () => {
      const theme = preferences.theme;
      let isDark: boolean;

      if (theme === "system") {
        isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      } else {
        isDark = theme === "dark";
      }

      document.documentElement.classList.toggle("dark", isDark);
      document.documentElement.classList.toggle("light", !isDark);
    };

    applyTheme();

    // Listen for system theme changes
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      if (preferences.theme === "system") {
        applyTheme();
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [preferences.theme]);

  const formatDate = useCallback(
    (date: Date | string): string => {
      const dateObj = typeof date === "string" ? new Date(date) : date;
      const day = String(dateObj.getDate()).padStart(2, "0");
      const month = String(dateObj.getMonth() + 1).padStart(2, "0");
      const year = dateObj.getFullYear();

      switch (preferences.dateFormat) {
        case "MM/DD/YYYY":
          return `${month}/${day}/${year}`;
        case "YYYY-MM-DD":
          return `${year}-${month}-${day}`;
        case "DD/MM/YYYY":
        default:
          return `${day}/${month}/${year}`;
      }
    },
    [preferences.dateFormat]
  );

  const formatPrice = useCallback(
    (price: number | string | null, symbol?: string): string => {
      if (price === null || price === undefined) {
        return preferences.currency === "INR" ? "₹--" : "$--";
      }

      const numPrice = typeof price === "string" ? parseFloat(price) : price;
      if (Number.isNaN(numPrice)) {
        return preferences.currency === "INR" ? "₹--" : "$--";
      }

      const currencySymbol = preferences.currency === "INR" ? "₹" : "$";
      let formatted: string;

      if (preferences.currency === "INR") {
        formatted = numPrice.toLocaleString("en-IN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      } else {
        formatted = numPrice.toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }

      return symbol ? `${currencySymbol}${formatted} ${symbol}` : `${currencySymbol}${formatted}`;
    },
    [preferences.currency]
  );

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
        formatDate,
        formatPrice,
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
