"use client";

import { useEffect, useState } from "react";
import { CircleAlert, Globe2, MapPin } from "lucide-react";
import { fetchCompanyProfile, type CompanyProfile } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CompanyProfileCard({ symbol }: { symbol: string }) {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    void fetchCompanyProfile(symbol)
      .then((result) => {
        if (active) setProfile(result);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [symbol]);

  if (error) {
    return <Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="flex items-center gap-2 p-5 text-sm text-muted-foreground"><CircleAlert className="size-4" /> Company profile is unavailable.</CardContent></Card>;
  }
  if (!profile) return <div className="h-48 animate-pulse rounded-xl border border-border/70 bg-card/60" />;
  const headquarters = [profile.headquarters_city, profile.headquarters_state, profile.headquarters_country].filter(Boolean).join(", ");
  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-sm text-cyan-300">Company profile</p><CardTitle className="mt-1">{profile.name}</CardTitle></div>
          <Badge variant="outline">{profile.data_freshness}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2 text-xs"><Badge variant="outline">{profile.exchange}</Badge>{profile.sector && <Badge variant="outline">{profile.sector}</Badge>}{profile.industry && <Badge variant="outline">{profile.industry}</Badge>}</div>
        {profile.business_summary && <p className="text-sm leading-6 text-muted-foreground">{profile.business_summary}</p>}
        <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><p className="text-xs text-muted-foreground">Headquarters</p><p className="mt-1">{headquarters || "Not reported"}</p></div>
          <div><p className="text-xs text-muted-foreground">Employees</p><p className="mt-1">{profile.employees == null ? "Not reported" : profile.employees.toLocaleString("en-IN")}</p></div>
          <div><p className="text-xs text-muted-foreground">Fiscal year end</p><p className="mt-1">{profile.fiscal_year_end ?? "Not reported"}</p></div>
          <div><p className="text-xs text-muted-foreground">Currency</p><p className="mt-1">{profile.currency ?? "Not reported"}</p></div>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          {profile.website && <a className="inline-flex items-center gap-1 text-cyan-300 hover:underline" href={profile.website} target="_blank" rel="noreferrer"><Globe2 className="size-3.5" /> Website</a>}
          {headquarters && <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" /> {headquarters}</span>}
        </div>
        <p className="text-xs text-muted-foreground">Profile metadata is sourced from Yahoo Finance and may be incomplete or stale.</p>
      </CardContent>
    </Card>
  );
}
