import { useEffect, useRef } from "react";
import { useUserPreferences } from "@/context/user-preferences-context";

/**
 * Hook to manage auto-refresh of data based on user preferences
 * @param callback Function to call when refresh interval is triggered
 */
export function useAutoRefresh(callback: () => void | Promise<void>) {
  const { preferences } = useUserPreferences();
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Clear existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Set up new interval if auto-refresh is enabled
    if (preferences.autoRefreshQuotes && preferences.autoRefreshInterval > 0) {
      const intervalMs = preferences.autoRefreshInterval * 60 * 1000; // Convert minutes to milliseconds
      
      // Call immediately first
      callback();
      
      // Then set up recurring interval
      intervalRef.current = setInterval(() => {
        callback();
      }, intervalMs);
    }

    // Cleanup on unmount or when preferences change
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [preferences.autoRefreshQuotes, preferences.autoRefreshInterval, callback]);

  return () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  };
}
