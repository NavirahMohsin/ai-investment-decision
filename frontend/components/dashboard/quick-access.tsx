import Link from "next/link";
import { ArrowUpRight, FileSearch, Newspaper, Sparkles, TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const links = [
  { title: "Explore Stocks", description: "Discover companies and market context.", href: "/stocks", icon: TrendingUp },
  { title: "Analyse Financial News", description: "Track signals across market coverage.", href: "/news", icon: Newspaper },
  { title: "Generate AI Research", description: "Build a research brief with ArthAI.", href: "/research", icon: FileSearch },
  { title: "Explore Predictions", description: "Review available model insights.", href: "/predictions", icon: Sparkles },
];

export function QuickAccess() {
  return (
    <section aria-labelledby="quick-access-title">
      <div className="mb-4">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-cyan-300">Get started</p>
        <h2 id="quick-access-title" className="mt-1 text-lg font-semibold">Quick access</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {links.map(({ title, description, href, icon: Icon }) => (
          <Link href={href} key={href} className="group">
            <Card className="h-full border-border/70 bg-card/80 shadow-none transition-colors group-hover:border-primary/50 group-hover:bg-card">
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <span className="flex size-9 items-center justify-center rounded-lg border border-cyan-300/20 bg-cyan-300/10 text-cyan-300"><Icon className="size-4" /></span>
                  <ArrowUpRight className="size-4 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-cyan-300" />
                </div>
                <h3 className="mt-5 font-medium text-foreground">{title}</h3>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
