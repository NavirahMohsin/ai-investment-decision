import { Suspense } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { NewsDetail } from "@/components/news/news-detail";

export default function NewsArticlePage() {
  return (
    <Suspense fallback={<div className="h-96 animate-pulse rounded-xl border border-border/70 bg-card/60" />}>
      <DashboardLayout title="Article Details"><NewsDetail /></DashboardLayout>
    </Suspense>
  );
}
