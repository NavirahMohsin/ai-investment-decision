import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { NewsIngestionMonitor } from "@/components/news/news-monitor";

export default function NewsIngestionRoute() {
  return <DashboardLayout title="Ingestion History"><NewsIngestionMonitor /></DashboardLayout>;
}
