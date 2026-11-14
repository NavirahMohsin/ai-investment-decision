"use client";

import { useUserPreferences } from "@/context/user-preferences-context";
import { Card } from "@/components/ui/card";

export function NotificationSettings() {
  const { preferences, updatePreferences } = useUserPreferences();

  return (
    <div className="space-y-6">
      {/* Enable Notifications */}
      <Card className="border-border/50 bg-card/50 p-6">
        <label className="mb-6 flex cursor-pointer items-start gap-4">
          <input
            type="checkbox"
            checked={preferences.enableNotifications}
            onChange={(e) =>
              updatePreferences({ enableNotifications: e.target.checked })
            }
            className="mt-1 h-4 w-4"
          />
          <div className="flex-1">
            <span className="block font-semibold text-foreground">
              Enable Notifications
            </span>
            <p className="text-sm text-muted-foreground">
              Receive alerts for significant market movements and watchlist changes
            </p>
          </div>
        </label>

        {preferences.enableNotifications && (
          <label className="flex cursor-pointer items-start gap-4">
            <input
              type="checkbox"
              checked={preferences.notificationSound}
              onChange={(e) =>
                updatePreferences({ notificationSound: e.target.checked })
              }
              className="mt-1 h-4 w-4"
            />
            <div className="flex-1">
              <span className="block font-medium text-foreground">
                Notification Sound
              </span>
              <p className="text-sm text-muted-foreground">
                Play sound when notifications arrive
              </p>
            </div>
          </label>
        )}
      </Card>

      {/* Notification Types */}
      {preferences.enableNotifications && (
        <Card className="border-border/50 bg-card/50 p-6">
          <h3 className="mb-4 font-semibold text-foreground">Alert Types</h3>
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-green-500"></span>
              Price target reached
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-orange-500"></span>
              Significant price movement (&gt;5%)
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-red-500"></span>
              Major news for your watchlist
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-blue-500"></span>
              Sector performance changes
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
