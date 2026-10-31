import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { NewsDashboard } from "@/components/news/news-dashboard";

export default function NewsPage() {
  return (
    <DashboardLayout title="News Intelligence">
      <NewsDashboard />
    </DashboardLayout>
  );
}
