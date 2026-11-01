import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { SectorIntelligence } from "@/components/sectors/sector-intelligence";

export default function SectorsPage() {
  return <DashboardLayout title="Sector intelligence"><div className="space-y-7"><div><p className="text-sm text-cyan-300">Market structure</p><h1 className="mt-2 text-3xl font-semibold">Sector intelligence</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Explore tracked sectors, company rankings, market movement and fundamental context.</p></div><SectorIntelligence /></div></DashboardLayout>;
}
