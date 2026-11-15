"use client";

import { useUserPreferences, type Theme, type DateFormat } from "@/context/user-preferences-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function AppearanceSettings() {
  const { preferences, updatePreferences } = useUserPreferences();

  const themes: { value: Theme; label: string; description: string }[] = [
    {
      value: "light",
      label: "Light",
      description: "Clean, bright interface",
    },
    {
      value: "dark",
      label: "Dark",
      description: "Easy on the eyes",
    },
    {
      value: "system",
      label: "System",
      description: "Match your device settings",
    },
  ];

  const dateFormats: { value: DateFormat; label: string }[] = [
    { value: "DD/MM/YYYY", label: "DD/MM/YYYY (14/11/2026)" },
    { value: "MM/DD/YYYY", label: "MM/DD/YYYY (11/14/2026)" },
    { value: "YYYY-MM-DD", label: "YYYY-MM-DD (2026-11-14)" },
  ];

  const currencies = [
    { value: "INR", label: "Indian Rupee (INR)" },
    { value: "USD", label: "US Dollar (USD)" },
  ];

  return (
    <div className="space-y-6">
      {/* Theme Selection */}
      <Card className="border-border/50 bg-card/50 p-6">
        <div className="mb-6">
          <h3 className="font-semibold text-foreground">Theme</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how the interface should look
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {themes.map((theme) => (
            <Button
              key={theme.value}
              variant={preferences.theme === theme.value ? "default" : "outline"}
              onClick={() => updatePreferences({ theme: theme.value })}
              className="h-auto flex-col items-start justify-start p-4 text-left"
            >
              <span className="font-medium">{theme.label}</span>
              <span className="text-xs text-muted-foreground">
                {theme.description}
              </span>
            </Button>
          ))}
        </div>
      </Card>

      {/* Date Format */}
      <Card className="border-border/50 bg-card/50 p-6">
        <div className="mb-6">
          <h3 className="font-semibold text-foreground">Date Format</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            How dates will be displayed across the platform
          </p>
        </div>
        <div className="space-y-3">
          {dateFormats.map((format) => (
            <label
              key={format.value}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-border/50 p-3 hover:bg-accent/50"
            >
              <input
                type="radio"
                name="dateFormat"
                value={format.value}
                checked={preferences.dateFormat === format.value}
                onChange={(e) =>
                  updatePreferences({ dateFormat: e.target.value as DateFormat })
                }
                className="h-4 w-4"
              />
              <span className="text-sm font-medium text-foreground">
                {format.label}
              </span>
            </label>
          ))}
        </div>
      </Card>

      {/* Currency */}
      <Card className="border-border/50 bg-card/50 p-6">
        <div className="mb-6">
          <h3 className="font-semibold text-foreground">Currency</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Primary currency for displaying prices
          </p>
        </div>
        <div className="space-y-3">
          {currencies.map((currency) => (
            <label
              key={currency.value}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-border/50 p-3 hover:bg-accent/50"
            >
              <input
                type="radio"
                name="currency"
                value={currency.value}
                checked={preferences.currency === currency.value}
                onChange={(e) =>
                  updatePreferences({
                    currency: e.target.value as "INR" | "USD",
                  })
                }
                className="h-4 w-4"
              />
              <span className="text-sm font-medium text-foreground">
                {currency.label}
              </span>
            </label>
          ))}
        </div>
      </Card>
    </div>
  );
}
