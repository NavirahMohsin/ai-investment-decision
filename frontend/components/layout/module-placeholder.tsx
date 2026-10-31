import { Construction } from "lucide-react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";

export function ModulePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <DashboardLayout title={title}>
      <section className="flex min-h-[55vh] items-center justify-center">
        <div className="max-w-md text-center">
          <div className="mx-auto flex size-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
            <Construction className="size-6" />
          </div>
          <h2 className="mt-6 text-2xl font-semibold">{title}</h2>
          <p className="mt-3 leading-6 text-muted-foreground">{description}</p>
          <p className="mt-5 text-sm font-medium text-cyan-300">Module under development</p>
        </div>
      </section>
    </DashboardLayout>
  );
}
