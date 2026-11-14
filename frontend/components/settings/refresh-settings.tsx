"use client";

import { useUserPreferences } from "@/context/user-preferences-context";
import { Card } from "@/components/ui/card";

export function RefreshSettings() {
  const { preferences, updatePreferences } = useUserPreferences();

  const intervals = [1, 2, 5, 10, 15, 30];

  return (
    <div className="space-y-6">
      {/* Auto-Refresh */}
      <Card className="border-border/50 bg-card/50 p-6">
        <div className="mb-6">
          <label className="flex cursor-pointer items-start gap-4">
            <input
              type="checkbox"
              checked={preferences.autoRefreshQuotes}
              onChange={(e) =>
                updatePreferences({ autoRefreshQuotes: e.target.checked })
              }
              className="mt-1 h-4 w-4"
            />
            <div className="flex-1">
              <span className="block font-semibold text-foreground">
                Auto-Refresh Quotes
              </span>
              <p className="text-sm text-muted-foreground">
                Automatically fetch latest stock quotes
              </p>
            </div>
          </label>
        </div>

        {preferences.autoRefreshQuotes && (
          <div>
            <label className="mb-4 block text-sm font-medium text-foreground">
              Refresh Interval
            </label>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
              {intervals.map((interval) => (
                <button
                  key={interval}
                  onClick={() =>
                    updatePreferences({ autoRefreshInterval: interval })
                  }
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    preferences.autoRefreshInterval === interval
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border/50 bg-card/50 text-foreground hover:bg-accent/50"
                  }`}
                >
                  {interval}m
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Quotes will update every {preferences.autoRefreshInterval} minutes
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
