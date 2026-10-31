import { Suspense } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { StockDetailRoute } from "@/components/stocks/stock-detail-route";

function DetailFallback() {
  return <div className="h-96 animate-pulse rounded-xl border border-border/70 bg-card/60" />;
}

export default function StockDetailPage() {
  return (
    <Suspense fallback={<DetailFallback />}>
      <DashboardLayout title="Stock Detail">
        <StockDetailRoute />
      </DashboardLayout>
    </Suspense>
  );
}
