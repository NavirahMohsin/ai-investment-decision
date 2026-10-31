"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bot,
  BrainCircuit,
  ChevronRight,
  FlaskConical,
  LayoutDashboard,
  LineChart,
  Settings,
  Sparkles,
  TrendingUp,
  X,
  type LucideIcon,
} from "lucide-react";
import { SheetClose } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

type NavigationItem = { label: string; href: string; icon: LucideIcon };
type NavigationGroup = { label: string; items: NavigationItem[] };

const navigation: NavigationGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard", href: "/", icon: LayoutDashboard },
      { label: "Stock Explorer", href: "/stocks", icon: TrendingUp },
      { label: "News Intelligence", href: "/news", icon: BrainCircuit },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { label: "Predictions", href: "/predictions", icon: LineChart },
      { label: "Financial Research", href: "/research", icon: FlaskConical },
      { label: "AI Agents", href: "/agents", icon: Bot },
      { label: "Model Evaluation", href: "/models", icon: BarChart3 },
    ],
  },
  {
    label: "System",
    items: [{ label: "Settings", href: "/settings", icon: Settings }],
  },
];

export function Sidebar({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();

  return (
    <aside className={cn("flex h-full flex-col bg-sidebar", mobile ? "w-full" : "w-64 border-r border-sidebar-border")}>
      <div className="flex h-18 items-center justify-between border-b border-sidebar-border px-6">
        <Link href="/" className="flex items-center gap-3" aria-label="ArthAI dashboard">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
            <Sparkles className="size-5" />
          </span>
          <span>
            <span className="block text-lg font-semibold tracking-tight text-sidebar-foreground">ArthAI</span>
            <span className="block text-[10px] font-medium uppercase tracking-[0.18em] text-cyan-400">Financial intelligence</span>
          </span>
        </Link>
        {mobile && (
          <SheetClose aria-label="Close navigation" className="rounded-md p-2 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground">
            <X className="size-5" />
          </SheetClose>
        )}
      </div>

      <nav className="flex-1 space-y-7 overflow-y-auto px-3 py-7" aria-label="Main navigation">
        {navigation.map((group) => (
          <div key={group.label}>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{group.label}</p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                      active
                        ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
                    )}
                  >
                    <Icon className={cn("size-4", active ? "text-cyan-400" : "text-muted-foreground group-hover:text-cyan-400")} />
                    <span>{item.label}</span>
                    {active && <ChevronRight className="ml-auto size-3.5 text-cyan-400" />}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border px-6 py-5">
        <p className="text-xs text-muted-foreground">ArthAI platform</p>
        <p className="mt-1 text-xs font-medium text-sidebar-foreground">Version v0.1.0</p>
      </div>
    </aside>
  );
}
