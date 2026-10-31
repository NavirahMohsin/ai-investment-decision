import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { NewsSourceMonitor } from "@/components/news/news-monitor";

export default function NewsSourcesRoute() {
  return <DashboardLayout title="News Sources"><NewsSourceMonitor /></DashboardLayout>;
}
