"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, CircleAlert } from "lucide-react";
import { checkBackend } from "@/lib/api";

type BackendState = "checking" | "connected" | "unavailable";

export function WelcomeSection() {
  const [state, setState] = useState<BackendState>("checking");

  useEffect(() => {
    let active = true;
    checkBackend()
      .then(() => active && setState("connected"))
      .catch(() => active && setState("unavailable"));
    return () => {
      active = false;
    };
  }, []);

  const status = {
    checking: { label: "Connecting...", icon: Activity, className: "text-amber-300", dot: "bg-amber-300" },
    connected: { label: "Backend connected", icon: CheckCircle2, className: "text-emerald-300", dot: "bg-emerald-300" },
    unavailable: { label: "Backend unavailable", icon: CircleAlert, className: "text-rose-300", dot: "bg-rose-300" },
  }[state];
  const StatusIcon = status.icon;

  return (
    <section className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
      <div className="max-w-3xl">
        <p className="mb-3 text-sm font-medium text-cyan-300">Good to have you here</p>
        <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">Financial Intelligence Workspace</h2>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">Your unified workspace for Indian market research, analytics and AI-powered insights.</p>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground/80">ArthAI brings research workflows, market context and intelligent analysis together so you can make clearer, more informed decisions.</p>
      </div>
      <div className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-card px-3 py-2 text-xs">
        <span className={`size-1.5 rounded-full ${status.dot}`} />
        <StatusIcon className={`size-3.5 ${status.className}`} />
        <span className={status.className}>{status.label}</span>
      </div>
    </section>
  );
}
