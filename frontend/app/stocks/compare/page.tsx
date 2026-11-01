"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { CompanyComparison } from "@/components/stocks/company-comparison";

function CompareContent() {
  const params = useSearchParams();
  const symbols = params.getAll("symbols").flatMap((value) => value.split(",")).map((value) => value.trim().toUpperCase()).filter(Boolean);
  return <DashboardLayout title="Company comparison"><div className="space-y-7"><div><p className="text-sm text-cyan-300">Fundamental intelligence</p><h1 className="mt-2 text-3xl font-semibold">Compare companies</h1><p className="mt-2 text-sm text-muted-foreground">Compare reported financial metrics without treating missing data as zero.</p></div><CompanyComparison initialSymbols={symbols} /></div></DashboardLayout>;
}

export default function ComparePage() {
  return <Suspense fallback={<DashboardLayout title="Company comparison"><div className="h-96 animate-pulse rounded-xl border border-border/70 bg-card/60" /></DashboardLayout>}><CompareContent /></Suspense>;
}
