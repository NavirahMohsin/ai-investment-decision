import { ArrowDownToLine, Building2, Gauge, TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const icons = { index: TrendingUp, sentiment: Gauge, companies: Building2 };

export function MarketStatCard({ label, type, value = "--", detail = "Awaiting data integration" }: { label: string; type: keyof typeof icons; value?: string; detail?: string }) {
  const Icon = icons[type];
  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-4 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
          </div>
          <span className="flex size-9 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
            <Icon className="size-4" />
          </span>
        </div>
        <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
          <ArrowDownToLine className="size-3.5 text-muted-foreground/60" />
          <span>{detail}</span>
        </div>
      </CardContent>
    </Card>
  );
}
