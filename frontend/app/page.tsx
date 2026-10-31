import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { QuickAccess } from "@/components/dashboard/quick-access";
import { MarketOverview } from "@/components/dashboard/market-overview";
import { WatchlistSection } from "@/components/dashboard/watchlist-section";
import { WelcomeSection } from "@/components/dashboard/welcome-section";

export default function Home() {
  return (
    <DashboardLayout title="Dashboard">
      <div className="space-y-8">
        <WelcomeSection />
        <MarketOverview />
        <WatchlistSection />
        <QuickAccess />
      </div>
    </DashboardLayout>
  );
}
