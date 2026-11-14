"use client";

import { useState } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { AppearanceSettings } from "@/components/settings/appearance-settings";
import { DashboardSettings } from "@/components/settings/dashboard-settings";
import { RefreshSettings } from "@/components/settings/refresh-settings";
import { NotificationSettings } from "@/components/settings/notification-settings";
import { useUserPreferences } from "@/context/user-preferences-context";
import { Button } from "@/components/ui/button";
import {
  Palette,
  LayoutDashboard,
  RefreshCw,
  Bell,
} from "lucide-react";

type SettingsTab = "appearance" | "dashboard" | "refresh" | "notifications";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("appearance");
  const { resetPreferences } = useUserPreferences();

  const tabs: { id: SettingsTab; label: string; icon: typeof Palette }[] = [
    { id: "appearance", label: "Appearance", icon: Palette },
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "refresh", label: "Auto-Refresh", icon: RefreshCw },
    { id: "notifications", label: "Notifications", icon: Bell },
  ];

  const handleResetPreferences = () => {
    if (
      confirm(
        "Are you sure you want to reset all settings to default? This action cannot be undone."
      )
    ) {
      resetPreferences();
    }
  };

  return (
    <DashboardLayout title="Settings">
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground">Settings</h1>
          <p className="mt-2 text-muted-foreground">
            Customize your ArthAI workspace and preferences
          </p>
        </div>

        {/* Tabs Navigation */}
        <div className="flex flex-wrap gap-2 border-b border-border/50">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 border-b-2 px-4 py-3 font-medium transition-colors ${
                  activeTab === tab.id
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div className="min-h-96">
          {activeTab === "appearance" && <AppearanceSettings />}
          {activeTab === "dashboard" && <DashboardSettings />}
          {activeTab === "refresh" && <RefreshSettings />}
          {activeTab === "notifications" && <NotificationSettings />}
        </div>

        {/* Reset Button */}
        <div className="border-t border-border/50 pt-8">
          <Button
            variant="destructive"
            onClick={handleResetPreferences}
            className="opacity-80 hover:opacity-100"
          >
            Reset All Settings to Default
          </Button>
          <p className="mt-2 text-sm text-muted-foreground">
            This will restore all settings to their original values.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
