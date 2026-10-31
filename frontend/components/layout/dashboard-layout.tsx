import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export function DashboardLayout({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="fixed inset-y-0 left-0 z-30 hidden md:block">
        <Sidebar />
      </div>
      <div className="md:pl-64">
        <Topbar title={title} />
        <main className="mx-auto max-w-[1600px] px-4 py-7 sm:px-8 sm:py-10">{children}</main>
      </div>
    </div>
  );
}
