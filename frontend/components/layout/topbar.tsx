"use client";

import { Bell, Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "@/components/layout/sidebar";

export function Topbar({ title }: { title: string }) {
  return (
    <header className="flex h-18 items-center justify-between border-b border-border/70 bg-background/90 px-4 backdrop-blur-md sm:px-8">
      <div className="flex items-center gap-3">
        <Sheet>
          <SheetTrigger render={<Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation" />}>
            <Menu className="size-5" />
          </SheetTrigger>
          <SheetContent side="left" className="w-72 border-sidebar-border bg-sidebar p-0 text-sidebar-foreground" showCloseButton={false}>
            <SheetTitle className="sr-only">ArthAI navigation</SheetTitle>
            <Sidebar mobile />
          </SheetContent>
        </Sheet>
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Workspace</p>
          <h1 className="text-base font-semibold text-foreground sm:text-lg">{title}</h1>
        </div>
      </div>
      <div className="flex items-center gap-1 sm:gap-3">
        <Button variant="ghost" size="icon" aria-label="Search">
          <Search className="size-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="size-4" />
        </Button>
        <div className="ml-1 flex size-8 items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-400/10 text-xs font-semibold text-cyan-300" aria-label="User avatar placeholder">
          AI
        </div>
      </div>
    </header>
  );
}
