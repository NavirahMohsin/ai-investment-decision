"use client";

import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { QuickAccess } from "@/components/dashboard/quick-access";
import { MarketOverview } from "@/components/dashboard/market-overview";
import { WatchlistSection } from "@/components/dashboard/watchlist-section";
import { WelcomeSection } from "@/components/dashboard/welcome-section";
import { FundamentalsSummary } from "@/components/dashboard/fundamentals-summary";
import { useUserPreferences } from "@/context/user-preferences-context";

export default function Home() {
  const { preferences } = useUserPreferences();

  // Determine layout spacing based on dashboard layout preference
  const spacingClass = {
    compact: "space-y-4",
    standard: "space-y-8",
    detailed: "space-y-12",
  }[preferences.defaultDashboardLayout];

  return (
    <DashboardLayout title="Dashboard">
      <div className={spacingClass}>
        <WelcomeSection />
        {preferences.showMarketStatus && <MarketOverview />}
        {preferences.showSectorPerformance && <FundamentalsSummary />}
        {preferences.showWatchlistPerformance && <WatchlistSection />}
        <QuickAccess />
      </div>
    </DashboardLayout>
  );
}
