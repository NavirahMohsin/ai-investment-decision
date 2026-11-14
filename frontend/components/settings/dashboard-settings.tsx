"use client";

import { useUserPreferences } from "@/context/user-preferences-context";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { UserPreferences } from "@/context/user-preferences-context";

export function DashboardSettings() {
  const { preferences, updatePreferences } = useUserPreferences();

  const layouts: {
    value: UserPreferences["defaultDashboardLayout"];
    label: string;
    description: string;
  }[] = [
    {
      value: "compact",
      label: "Compact",
      description: "Minimize widget spacing and content",
    },
    {
      value: "standard",
      label: "Standard",
      description: "Balanced view with moderate spacing",
    },
    {
      value: "detailed",
      label: "Detailed",
      description: "Maximize information density",
    },
  ];

  const widgetOptions = [
    {
      key: "showMarketStatus" as const,
      label: "Market Status",
      description: "Display market overview and indices",
    },
    {
      key: "showSectorPerformance" as const,
      label: "Sector Performance",
      description: "Show sector-wise performance metrics",
    },
    {
      key: "showRecentNews" as const,
      label: "Recent News",
      description: "Display latest financial news",
    },
    {
      key: "showWatchlistPerformance" as const,
      label: "Watchlist Performance",
      description: "Show your watchlist summary",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Layout */}
      <Card className="border-border/50 bg-card/50 p-6">
        <div className="mb-6">
          <h3 className="font-semibold text-foreground">Dashboard Layout</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how information is displayed on the dashboard
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {layouts.map((layout) => (
            <Button
              key={layout.value}
              variant={
                preferences.defaultDashboardLayout === layout.value
                  ? "default"
                  : "outline"
              }
              onClick={() =>
                updatePreferences({ defaultDashboardLayout: layout.value })
              }
              className="h-auto flex-col items-start justify-start p-4 text-left"
            >
              <span className="font-medium">{layout.label}</span>
              <span className="text-xs text-muted-foreground">
                {layout.description}
              </span>
            </Button>
          ))}
        </div>
      </Card>

      {/* Widgets */}
      <Card className="border-border/50 bg-card/50 p-6">
        <div className="mb-6">
          <h3 className="font-semibold text-foreground">Dashboard Widgets</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Control which widgets appear on your dashboard
          </p>
        </div>
        <div className="space-y-4">
          {widgetOptions.map((widget) => (
            <label
              key={widget.key}
              className="flex cursor-pointer items-start gap-4 rounded-lg border border-border/50 p-4 hover:bg-accent/50"
            >
              <input
                type="checkbox"
                checked={preferences[widget.key]}
                onChange={(e) =>
                  updatePreferences({
                    [widget.key]: e.target.checked,
                  })
                }
                className="mt-1 h-4 w-4"
              />
              <div className="flex-1">
                <span className="block font-medium text-foreground">
                  {widget.label}
                </span>
                <p className="text-sm text-muted-foreground">
                  {widget.description}
                </p>
              </div>
            </label>
          ))}
        </div>
      </Card>
    </div>
  );
}
