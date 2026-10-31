import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { StockExplorer } from "@/components/stocks/stock-explorer";

export default function StocksPage() {
  return (
    <DashboardLayout title="Stock Explorer">
      <StockExplorer />
    </DashboardLayout>
  );
}
